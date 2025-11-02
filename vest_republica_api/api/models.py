from extensions import db
from datetime import datetime

class RepublicaCalouros(db.Model):
    __tablename__ = 'republica_calouros'
    
    id = db.Column(db.Integer, primary_key=True)
    republica_id = db.Column(db.Integer, db.ForeignKey('republicas.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String)
    phone = db.Column(db.String)
    course = db.Column(db.String, nullable=False)
    university = db.Column(db.String, nullable=False)
    campus = db.Column(db.String, nullable=False)
    entrance_year = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.Enum('male', 'female', 'other', name='gender_type'), nullable=False)
    status = db.Column(db.Enum('pending', 'contacted', 'interviewed', 'accepted', 'rejected', name='calouro_status_type'), default='pending')
    notes = db.Column(db.Text)
    contact_date = db.Column(db.Date)
    interview_date = db.Column(db.DateTime)
    favourite = db.Column(db.Boolean, nullable=False, default=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserFilters(db.Model):
    __tablename__ = 'user_filters'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String, nullable=False)
    filter_type = db.Column(db.Enum('calouros', 'republicas', name='filter_type_enum'), nullable=False)
    filters = db.Column(db.JSON, nullable=False)
    is_shared = db.Column(db.Boolean, default=False)
    share_token = db.Column(db.String)
    usage_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)