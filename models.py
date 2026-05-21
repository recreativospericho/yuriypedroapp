# -*- coding: utf-8 -*-
from datetime import datetime, date
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class Usuario(db.Model):
    __tablename__ = "usuarios"
    id          = db.Column(db.Integer, primary_key=True)
    nombre      = db.Column(db.String(60), nullable=False)
    iniciales   = db.Column(db.String(4), nullable=False)   # TU / YU / EM
    rol         = db.Column(db.String(20), default="empleado")  # admin / socio / empleado
    pin_hash    = db.Column(db.String(200), nullable=False)
    color       = db.Column(db.String(20), default="#F59E0B")

    def set_pin(self, pin):
        self.pin_hash = generate_password_hash(str(pin))

    def check_pin(self, pin):
        return check_password_hash(self.pin_hash, str(pin))


class Factura(db.Model):
    __tablename__ = "facturas"
    id          = db.Column(db.Integer, primary_key=True)
    numero      = db.Column(db.String(25), unique=True, nullable=False)
    tienda      = db.Column(db.String(40), nullable=False)   # Pinatar / Horadada
    fecha       = db.Column(db.Date, nullable=False, default=date.today)
    total_iva   = db.Column(db.Float, default=0.0)   # importe que paga JYSK (IVA incluido)
    base        = db.Column(db.Float, default=0.0)   # total_iva / 1.21
    iva         = db.Column(db.Float, default=0.0)   # total_iva - base
    concepto    = db.Column(db.String(300), default="Servicios de reposición, merchandising y mantenimiento")
    estado      = db.Column(db.String(20), default="pendiente")  # pendiente / enviada / cobrada
    fecha_envio = db.Column(db.Date, nullable=True)   # cuando se envió a JYSK
    user_id     = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    creado_en   = db.Column(db.DateTime, default=datetime.utcnow)
    usuario     = db.relationship("Usuario", foreign_keys=[user_id])


class Gasto(db.Model):
    __tablename__ = "gastos"
    id          = db.Column(db.Integer, primary_key=True)
    fecha       = db.Column(db.Date, nullable=False, default=date.today)
    categoria   = db.Column(db.String(40), nullable=False)
    importe     = db.Column(db.Float, nullable=False)
    descripcion = db.Column(db.String(300))
    tienda      = db.Column(db.String(40))
    foto_b64    = db.Column(db.Text)   # foto del ticket
    user_id     = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario     = db.relationship("Usuario", foreign_keys=[user_id])


class KmViaje(db.Model):
    __tablename__ = "km_viajes"
    id          = db.Column(db.Integer, primary_key=True)
    fecha       = db.Column(db.Date, nullable=False, default=date.today)
    tienda      = db.Column(db.String(40), nullable=False)
    km_inicio   = db.Column(db.Float, default=0.0)
    km_fin      = db.Column(db.Float, default=0.0)
    km_total    = db.Column(db.Float, default=0.0)
    notas       = db.Column(db.String(300))
    user_id     = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario     = db.relationship("Usuario", foreign_keys=[user_id])


class ParteTrabajo(db.Model):
    __tablename__ = "partes_trabajo"
    id              = db.Column(db.Integer, primary_key=True)
    fecha           = db.Column(db.Date, nullable=False, default=date.today)
    tienda          = db.Column(db.String(40), nullable=False)
    personas        = db.Column(db.String(100))   # "Pedro,Yuri" / "Pedro,Empleado" etc.
    hora_entrada    = db.Column(db.String(10))
    hora_salida     = db.Column(db.String(10))
    # Portes y montajes del día (expresión + total IVA incluido)
    portes_texto    = db.Column(db.String(300))   # "30+40+50+300"
    total_portes    = db.Column(db.Float, default=0.0)   # suma IVA incluido
    # Desglose de gastos del día
    gasto_gasoil    = db.Column(db.Float, default=0.0)
    gasto_furgoneta = db.Column(db.Float, default=0.0)
    gasto_empleado  = db.Column(db.Float, default=60.0)
    # Otros
    tareas          = db.Column(db.Text)
    incidencias     = db.Column(db.Text)
    user_id         = db.Column(db.Integer, db.ForeignKey("usuarios.id"))
    usuario         = db.relationship("Usuario", foreign_keys=[user_id])

    @property
    def total_gastos(self):
        return (self.gasto_gasoil or 0) + (self.gasto_furgoneta or 0) + (self.gasto_empleado or 0)

    @property
    def total_portes_base(self):
        return round((self.total_portes or 0) / 1.21, 2)

    @property
    def resultado_dia(self):
        return round(self.total_portes_base - self.total_gastos, 2)


class Config(db.Model):
    __tablename__ = "config"
    clave = db.Column(db.String(60), primary_key=True)
    valor = db.Column(db.Text)
