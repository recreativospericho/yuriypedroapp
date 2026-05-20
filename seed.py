# -*- coding: utf-8 -*-
from models import db, Usuario, Config


def seed_usuarios():
    if Usuario.query.count() > 0:
        return
    usuarios = [
        dict(nombre="Pedro",   iniciales="TU", rol="admin",    pin="1234", color="#F59E0B"),
        dict(nombre="Yuri",    iniciales="YU", rol="socio",    pin="5678", color="#3B82F6"),
        dict(nombre="Empleado",iniciales="EM", rol="empleado", pin="9999", color="#6B7280"),
    ]
    for u in usuarios:
        obj = Usuario(nombre=u["nombre"], iniciales=u["iniciales"],
                      rol=u["rol"], color=u["color"])
        obj.set_pin(u["pin"])
        db.session.add(obj)
    db.session.commit()
    print(f"✅ {len(usuarios)} usuarios creados.")


def seed_config():
    defaults = {
        "EMPRESA_NOMBRE": "Retail Service",
        "EMPRESA_NIF":    "20517937M",
        "EMPRESA_DIR":    "Calle Villajoyosa 41, Pilar de la Horadada, Alicante",
        "EMPRESA_TEL":    "655097618",
        "FACTURA_SERIE":  "F",
        "IVA_PCT":        "21",
    }
    for k, v in defaults.items():
        if not Config.query.get(k):
            db.session.add(Config(clave=k, valor=v))
    db.session.commit()
    print("✅ Config inicial creada.")


def seed_all():
    seed_usuarios()
    seed_config()
