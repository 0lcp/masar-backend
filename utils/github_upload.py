"""
رفع الملفات (PDF وغيرها) إلى ريبو GitHub منفصل مخصص لتخزين ملفات
الملازم والوزاريات، باستخدام Git Data API (Blobs → Tree → Commit → Ref)
بدل الـ Contents API البسيطة — هذا يدعم ملفات لين 100 ميغا بدل حد
الـ ~25 ميغا للطريقة المباشرة.

يحتاج إعداد هذي المتغيرات بالـ config / متغيرات البيئة:
    GITHUB_TOKEN        -> Personal Access Token عنده صلاحية "repo"
    GITHUB_FILES_REPO   -> اسم الريبو بصيغة "owner/repo" (مثلاً: "0lcp/masar-files")
    GITHUB_FILES_BRANCH -> اسم الفرع (اختياري، افتراضي "main")
"""

import base64
import time
import uuid

import requests
from flask import current_app

GITHUB_API = "https://api.github.com"


class GithubUploadError(Exception):
    pass


def _headers():
    token = current_app.config.get("GITHUB_TOKEN")
    if not token:
        raise GithubUploadError("GITHUB_TOKEN غير معرّف بإعدادات السيرفر")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo():
    repo = current_app.config.get("GITHUB_FILES_REPO")
    if not repo:
        raise GithubUploadError("GITHUB_FILES_REPO غير معرّف بإعدادات السيرفر")
    return repo


def _branch():
    return current_app.config.get("GITHUB_FILES_BRANCH", "main")


def _safe_filename(original_filename: str) -> str:
    """
    يولّد اسم ملف فريد (يمنع تعارض/استبدال ملفات بنفس الاسم)
    مع الحفاظ على الامتداد الأصلي.
    """
    ext = ""
    if "." in original_filename:
        ext = "." + original_filename.rsplit(".", 1)[-1].lower()
    unique = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    return f"{unique}{ext}"


def upload_file_to_github(file_bytes: bytes, original_filename: str, folder: str = "misc"):
    """
    يرفع ملف (bytes) إلى ريبو GitHub المخصص للملفات، ويرجع
    (رابط التحميل المباشر, حجم الملف بالكيلوبايت).

    folder: اسم مجلد داخل الريبو لتنظيم الملفات (مثلاً "library" أو "wazari").
    """
    if not file_bytes:
        raise GithubUploadError("الملف فاضي")

    max_bytes = 100 * 1024 * 1024  # 100 ميغا (حد GitHub الأقصى لكل ملف)
    if len(file_bytes) > max_bytes:
        raise GithubUploadError("حجم الملف أكبر من 100 ميغا — الحد الأقصى المسموح")

    repo = _repo()
    branch = _branch()
    headers = _headers()
    filename = _safe_filename(original_filename)
    path = f"{folder}/{filename}"

    # 1) نجيب آخر commit بالفرع
    ref_res = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/refs/heads/{branch}",
        headers=headers, timeout=30,
    )
    if ref_res.status_code != 200:
        raise GithubUploadError(f"تعذر جلب الفرع: {ref_res.text}")
    latest_commit_sha = ref_res.json()["object"]["sha"]

    # 2) نجيب الـ tree الأساسي المرتبط بآخر commit
    commit_res = requests.get(
        f"{GITHUB_API}/repos/{repo}/git/commits/{latest_commit_sha}",
        headers=headers, timeout=30,
    )
    if commit_res.status_code != 200:
        raise GithubUploadError(f"تعذر جلب الـ commit: {commit_res.text}")
    base_tree_sha = commit_res.json()["tree"]["sha"]

    # 3) ننشئ blob (محتوى الملف) بصيغة base64
    encoded_content = base64.b64encode(file_bytes).decode("utf-8")
    blob_res = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/blobs",
        headers=headers,
        json={"content": encoded_content, "encoding": "base64"},
        timeout=60,
    )
    if blob_res.status_code != 201:
        raise GithubUploadError(f"فشل رفع محتوى الملف: {blob_res.text}")
    blob_sha = blob_res.json()["sha"]

    # 4) ننشئ tree جديد يضيف الملف الجديد فوق الـ tree الأساسي
    tree_res = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/trees",
        headers=headers,
        json={
            "base_tree": base_tree_sha,
            "tree": [{
                "path": path,
                "mode": "100644",
                "type": "blob",
                "sha": blob_sha,
            }],
        },
        timeout=30,
    )
    if tree_res.status_code != 201:
        raise GithubUploadError(f"فشل إنشاء الـ tree: {tree_res.text}")
    new_tree_sha = tree_res.json()["sha"]

    # 5) ننشئ commit جديد فوق آخر commit موجود
    commit_create_res = requests.post(
        f"{GITHUB_API}/repos/{repo}/git/commits",
        headers=headers,
        json={
            "message": f"رفع ملف: {path}",
            "tree": new_tree_sha,
            "parents": [latest_commit_sha],
        },
        timeout=30,
    )
    if commit_create_res.status_code != 201:
        raise GithubUploadError(f"فشل إنشاء الـ commit: {commit_create_res.text}")
    new_commit_sha = commit_create_res.json()["sha"]

    # 6) نحرّك الفرع للـ commit الجديد
    update_ref_res = requests.patch(
        f"{GITHUB_API}/repos/{repo}/git/refs/heads/{branch}",
        headers=headers,
        json={"sha": new_commit_sha},
        timeout=30,
    )
    if update_ref_res.status_code != 200:
        raise GithubUploadError(f"فشل تحديث الفرع: {update_ref_res.text}")

    file_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
    size_kb = round(len(file_bytes) / 1024)

    return file_url, size_kb
