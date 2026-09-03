from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail

# تعريف الكائنات المشتركة
db = SQLAlchemy()
mail = Mail()
