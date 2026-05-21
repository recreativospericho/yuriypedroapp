# -*- coding: utf-8 -*-
import os
from datetime import date, datetime, timedelta
from functools import wraps
from flask import (Flask, render_template, request, redirect,
                   url_for, flash, session, jsonify, send_file)
from models import db, Usuario, Factura, Gasto, KmViaje, ParteTrabajo, Config
from seed import seed_all

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "rs-secret-2026")

raw_db = os.environ.get("DATABASE_URL", "sqlite:///retail.db")
if raw_db.startswith("postgres://"):
    raw_db = raw_db.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = raw_db
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def get_config(clave, defecto=""):
    c = Config.query.get(clave)
    return c.valor if c else defecto


def set_config(clave, valor):
    c = Config.query.get(clave)
    if c:
        c.valor = valor
    else:
        db.session.add(Config(clave=clave, valor=valor))
    db.session.commit()


def next_factura():
    serie = get_config("FACTURA_SERIE", "F")
    año   = date.today().year
    ultima = (Factura.query
              .filter(Factura.numero.like(f"{serie}-{año}-%"))
              .order_by(Factura.numero.desc()).first())
    if ultima:
        n = int(ultima.numero.split("-")[-1]) + 1
    else:
        n = 1
    return f"{serie}-{año}-{n:03d}"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def solo_socios(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_rol") not in ("admin", "socio"):
            flash("Acceso restringido a socios.", "warning")
            return redirect(url_for("facturas"))
        return f(*args, **kwargs)
    return decorated


def usuario_actual():
    uid = session.get("user_id")
    return Usuario.query.get(uid) if uid else None


app.jinja_env.globals["usuario_actual"] = usuario_actual
app.jinja_env.globals["get_config"]     = get_config
app.jinja_env.globals["enumerate"]      = enumerate


@app.route("/logo-png")
def logo_png():
    """Sirve el logo SVG como imagen para la marca de agua."""
    svg = """<svg xmlns='http://www.w3.org/2000/svg' width='300' height='100' viewBox='0 0 300 100'>
  <rect width='300' height='100' rx='8' fill='#111827'/>
  <rect x='10' y='18' width='64' height='64' rx='6' fill='#F59E0B'/>
  <text x='42' y='62' font-family='Arial Black,sans-serif' font-size='28' font-weight='900'
        fill='#111827' text-anchor='middle'>RS</text>
  <text x='90' y='48' font-family='Arial,sans-serif' font-size='22' font-weight='700'
        fill='#FFFFFF' dominant-baseline='middle'>RETAIL</text>
  <text x='90' y='72' font-family='Arial,sans-serif' font-size='15' font-weight='400'
        fill='#F59E0B' dominant-baseline='middle' letter-spacing='4'>SERVICE</text>
  <line x1='90' y1='85' x2='290' y2='85' stroke='#F59E0B' stroke-width='2'/>
</svg>"""
    from flask import Response
    return Response(svg, mimetype="image/svg+xml")


# ─── Login / Logout ───────────────────────────────────────────────────────────
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    usuarios = Usuario.query.order_by(Usuario.id).all()
    if request.method == "POST":
        uid = int(request.form["user_id"])
        pin = request.form.get("pin", "")
        u   = Usuario.query.get(uid)
        if u and u.check_pin(pin):
            session["user_id"]   = u.id
            session["user_nombre"]= u.nombre
            session["user_rol"]  = u.rol
            session["user_ini"]  = u.iniciales
            # Empleado va directo a gastos (solo puede ver gastos)
            if u.rol == "empleado":
                return redirect(url_for("gastos"))
            return redirect(url_for("dashboard"))
        flash("PIN incorrecto.", "danger")
    return render_template("login.html", usuarios=usuarios)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ─── Dashboard ────────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
@solo_socios
def dashboard():
    hoy    = date.today()
    mes    = hoy.month
    año    = hoy.year
    f_ini  = date(año, mes, 1)
    f_fin  = date(año + (1 if mes == 12 else 0), (mes % 12) + 1, 1) - timedelta(days=1)

    facturas_mes  = Factura.query.filter(Factura.fecha >= f_ini, Factura.fecha <= f_fin).all()
    gastos_mes    = Gasto.query.filter(Gasto.fecha >= f_ini, Gasto.fecha <= f_fin).all()

    ingresos      = sum(f.total_iva for f in facturas_mes)
    ingresos_base = sum(f.base for f in facturas_mes)
    iva_cobrado   = sum(f.iva for f in facturas_mes)
    gastos_tot    = sum(g.importe for g in gastos_mes)
    pendientes    = sum(f.total_iva for f in facturas_mes if f.estado == "pendiente")
    cobradas      = sum(f.total_iva for f in facturas_mes if f.estado == "cobrada")

    km_mes        = KmViaje.query.filter(KmViaje.fecha >= f_ini, KmViaje.fecha <= f_fin).all()
    km_total      = sum(k.km_total for k in km_mes)

    # Todas las facturas no cobradas (pendientes + enviadas)
    proximas      = (Factura.query.filter(Factura.estado != "cobrada")
                    .order_by(Factura.fecha).all())
    total_pendiente_cobro = sum(f.total_iva for f in proximas)

    meses_nombres = ["Ene","Feb","Mar","Abr","May","Jun",
                     "Jul","Ago","Sep","Oct","Nov","Dic"]
    return render_template("dashboard.html",
        total_pendiente_cobro=total_pendiente_cobro,
        hoy=hoy, mes_nombre=meses_nombres[mes-1], año=año,
        ingresos=ingresos, ingresos_base=ingresos_base,
        iva_cobrado=iva_cobrado, gastos_tot=gastos_tot,
        pendientes=pendientes, cobradas=cobradas,
        km_total=km_total, proximas=proximas,
        n_facturas=len(facturas_mes))


# ─── Facturas ─────────────────────────────────────────────────────────────────
@app.route("/facturas")
@login_required
@solo_socios
def facturas():
    tienda = request.args.get("tienda", "")
    estado = request.args.get("estado", "")
    q = Factura.query
    if tienda: q = q.filter_by(tienda=tienda)
    if estado: q = q.filter_by(estado=estado)
    lista = q.order_by(Factura.fecha.desc()).all()
    return render_template("facturas.html", facturas=lista,
                           tienda=tienda, estado=estado, hoy=date.today())


@app.route("/facturas/nueva", methods=["POST"])
@login_required
@solo_sociosdef factura_nueva():
    total_iva = float(request.form.get("total_iva", 0) or 0)
    iva_pct   = float(get_config("IVA_PCT", "21")) / 100
    base      = round(total_iva / (1 + iva_pct), 2)
    iva       = round(total_iva - base, 2)
    f = Factura(
        numero   = next_factura(),
        tienda   = request.form["tienda"],
        fecha    = date.fromisoformat(request.form["fecha"]),
        total_iva= total_iva,
        base     = base,
        iva      = iva,
        concepto = request.form.get("concepto", "Transporte y montaje de muebles"),
        estado   = "pendiente",
        user_id  = session["user_id"],
    )
    db.session.add(f)
    db.session.commit()
    flash(f"Factura {f.numero} creada — Base: {base:.2f} € + IVA: {iva:.2f} €", "success")
    return redirect(url_for("facturas"))


@app.route("/facturas/<int:fid>/cobrar", methods=["POST"])
@login_required
@solo_socios
def factura_cobrar(fid):
    f = Factura.query.get_or_404(fid)
    f.estado = "cobrada"
    db.session.commit()
    flash(f"Factura {f.numero} marcada como cobrada.", "success")
    return redirect(url_for("facturas"))


@app.route("/facturas/<int:fid>/enviar", methods=["POST"])
@login_required
@solo_socios
def factura_enviar(fid):
    f = Factura.query.get_or_404(fid)
    f.estado      = "enviada"
    f.fecha_envio = date.today()
    db.session.commit()
    flash(f"Factura {f.numero} marcada como enviada a JYSK ({date.today().strftime('%d/%m/%Y')}).", "success")
    return redirect(url_for("facturas"))


@app.route("/facturas/<int:fid>/eliminar", methods=["POST"])
@login_required
@solo_socios
def factura_eliminar(fid):
    f = Factura.query.get_or_404(fid)
    db.session.delete(f)
    db.session.commit()
    flash("Factura eliminada.", "info")
    return redirect(url_for("facturas"))


@app.route("/facturas/<int:fid>/pdf")
@login_required
def factura_pdf(fid):
    from pdf_gen import generar_factura
    f   = Factura.query.get_or_404(fid)
    buf = generar_factura(f)
    return send_file(buf, mimetype="application/pdf",
                     download_name=f"{f.numero}.pdf")


# ─── Gastos ───────────────────────────────────────────────────────────────────
@app.route("/gastos")
@login_required
def gastos():
    tienda = request.args.get("tienda", "")
    cat    = request.args.get("cat", "")
    q = Gasto.query
    if tienda: q = q.filter_by(tienda=tienda)
    if cat:    q = q.filter_by(categoria=cat)
    lista = q.order_by(Gasto.fecha.desc()).all()
    total = sum(g.importe for g in lista)
    categorias = ["combustible","materiales","furgoneta","seguro","gestoria","renting","otros"]
    return render_template("gastos.html", gastos=lista, total=total,
                           categorias=categorias, tienda=tienda, cat=cat,
                           hoy=date.today())


@app.route("/gastos/nuevo", methods=["POST"])
@login_required
def gasto_nuevo():
    import base64
    foto_b64 = None
    if "foto" in request.files and request.files["foto"].filename:
        foto = request.files["foto"]
        mime = foto.content_type or "image/jpeg"
        foto_b64 = f"data:{mime};base64," + base64.b64encode(foto.read()).decode()
    g = Gasto(
        fecha       = date.fromisoformat(request.form["fecha"]),
        categoria   = request.form["categoria"],
        importe     = float(request.form.get("importe", 0) or 0),
        descripcion = request.form.get("descripcion", ""),
        tienda      = request.form.get("tienda", ""),
        foto_b64    = foto_b64,
        user_id     = session["user_id"],
    )
    db.session.add(g)
    db.session.commit()
    flash(f"Gasto de {g.importe:.2f} € registrado.", "success")
    return redirect(url_for("gastos"))


@app.route("/gastos/<int:gid>/eliminar", methods=["POST"])
@login_required
@solo_socios
def gasto_eliminar(gid):
    g = Gasto.query.get_or_404(gid)
    db.session.delete(g)
    db.session.commit()
    flash("Gasto eliminado.", "info")
    return redirect(url_for("gastos"))


# ─── Km / Vehículo ────────────────────────────────────────────────────────────
@app.route("/km")
@login_required
@solo_socios
def km():
    lista = KmViaje.query.order_by(KmViaje.fecha.desc()).limit(50).all()
    total_km = sum(k.km_total for k in KmViaje.query.all())
    return render_template("km.html", viajes=lista, total_km=total_km, hoy=date.today())


@app.route("/km/nuevo", methods=["POST"])
@login_required
def km_nuevo():
    ki = float(request.form.get("km_inicio", 0) or 0)
    kf = float(request.form.get("km_fin",    0) or 0)
    v  = KmViaje(
        fecha     = date.fromisoformat(request.form["fecha"]),
        tienda    = request.form["tienda"],
        km_inicio = ki,
        km_fin    = kf,
        km_total  = max(kf - ki, 0),
        notas     = request.form.get("notas", ""),
        user_id   = session["user_id"],
    )
    db.session.add(v)
    db.session.commit()
    flash(f"Viaje registrado: {v.km_total:.1f} km", "success")
    return redirect(url_for("km"))


@app.route("/km/<int:kid>/eliminar", methods=["POST"])
@login_required
def km_eliminar(kid):
    k = KmViaje.query.get_or_404(kid)
    db.session.delete(k)
    db.session.commit()
    return redirect(url_for("km"))


# ─── Agenda / Partes ──────────────────────────────────────────────────────────
@app.route("/agenda")
@login_required
@solo_socios
def agenda():
    hoy    = date.today()
    lunes  = hoy - timedelta(days=hoy.weekday())
    semana = [lunes + timedelta(days=i) for i in range(7)]
    partes_semana = ParteTrabajo.query.filter(
        ParteTrabajo.fecha >= lunes,
        ParteTrabajo.fecha <= lunes + timedelta(days=6)
    ).order_by(ParteTrabajo.fecha).all()
    usuarios = Usuario.query.order_by(Usuario.id).all()
    return render_template("agenda.html", hoy=hoy, semana=semana,
                           partes_semana=partes_semana, usuarios=usuarios)


@app.route("/parte/<int:pid>/eliminar", methods=["POST"])
@login_required
def parte_eliminar(pid):
    p = ParteTrabajo.query.get_or_404(pid)
    db.session.delete(p)
    db.session.commit()
    flash("Parte eliminado.", "info")
    return redirect(url_for("agenda"))


@app.route("/parte/<int:pid>/editar", methods=["GET", "POST"])
@login_required
def parte_editar(pid):
    p       = ParteTrabajo.query.get_or_404(pid)
    usuarios = Usuario.query.order_by(Usuario.id).all()
    if request.method == "POST":
        import re
        portes_texto = request.form.get("portes_texto", "").strip()
        nums = re.findall(r'[\d]+(?:[.,]\d+)?', portes_texto.replace(",", "."))
        p.fecha           = date.fromisoformat(request.form["fecha"])
        p.tienda          = request.form["tienda"]
        p.personas        = ",".join(request.form.getlist("personas"))
        p.hora_entrada    = request.form.get("hora_entrada", "")
        p.hora_salida     = request.form.get("hora_salida", "")
        p.portes_texto    = portes_texto
        p.total_portes    = sum(float(n) for n in nums)
        p.gasto_gasoil    = float(request.form.get("gasto_gasoil", 0) or 0)
        p.gasto_furgoneta = float(request.form.get("gasto_furgoneta", 0) or 0)
        p.gasto_empleado  = float(request.form.get("gasto_empleado", 60) or 60)
        p.tareas          = request.form.get("tareas", "")
        p.incidencias     = request.form.get("incidencias", "")
        db.session.commit()
        flash("Parte actualizado.", "success")
        return redirect(url_for("agenda"))
    return render_template("parte_editar.html", p=p, usuarios=usuarios)


@app.route("/parte/nuevo", methods=["POST"])
@login_required
def parte_nuevo():
    # Calcular total portes desde la expresión
    portes_texto = request.form.get("portes_texto", "").strip()
    total_portes = 0.0
    if portes_texto:
        import re
        nums = re.findall(r'[\d]+(?:[.,]\d+)?', portes_texto.replace(",", "."))
        total_portes = sum(float(n) for n in nums)

    personas = ",".join(request.form.getlist("personas"))

    p = ParteTrabajo(
        fecha           = date.fromisoformat(request.form["fecha"]),
        tienda          = request.form["tienda"],
        personas        = personas,
        hora_entrada    = request.form.get("hora_entrada", ""),
        hora_salida     = request.form.get("hora_salida", ""),
        portes_texto    = portes_texto,
        total_portes    = total_portes,
        gasto_gasoil    = float(request.form.get("gasto_gasoil", 0) or 0),
        gasto_furgoneta = float(request.form.get("gasto_furgoneta", 0) or 0),
        gasto_empleado  = float(request.form.get("gasto_empleado", 60) or 60),
        tareas          = request.form.get("tareas", ""),
        incidencias     = request.form.get("incidencias", ""),
        user_id         = session["user_id"],
    )
    db.session.add(p)
    db.session.commit()
    flash(f"Parte guardado — Portes: {total_portes:.2f} € (IVA inc.) · Gastos: {p.total_gastos:.2f} €", "success")
    return redirect(url_for("agenda"))


# ─── Ajustes ──────────────────────────────────────────────────────────────────
@app.route("/ajustes", methods=["GET", "POST"])
@login_required
@solo_socios
def ajustes():
    if request.method == "POST":
        for k in ["EMPRESA_NOMBRE","EMPRESA_NIF","EMPRESA_DIR","EMPRESA_TEL"]:
            v = request.form.get(k, "").strip()
            if v: set_config(k, v)
        flash("Datos actualizados.", "success")
    usuarios = Usuario.query.all()
    return render_template("ajustes.html", usuarios=usuarios)


@app.route("/ajustes/pin", methods=["POST"])
@login_required
def cambiar_pin():
    uid     = int(request.form.get("user_id", session["user_id"]))
    pin_act = request.form.get("pin_actual", "")
    pin_new = request.form.get("pin_nuevo", "")
    u = Usuario.query.get_or_404(uid)
    # Solo admin puede cambiar PIN de otros; socios solo el suyo
    if uid != session["user_id"] and session.get("user_rol") != "admin":
        flash("Solo puedes cambiar tu propio PIN.", "danger")
        return redirect(url_for("ajustes"))
    if not u.check_pin(pin_act):
        flash("PIN actual incorrecto.", "danger")
        return redirect(url_for("ajustes"))
    if len(str(pin_new)) != 4 or not str(pin_new).isdigit():
        flash("El PIN debe tener exactamente 4 dígitos.", "danger")
        return redirect(url_for("ajustes"))
    u.set_pin(pin_new)
    db.session.commit()
    flash(f"PIN de {u.nombre} actualizado.", "success")
    return redirect(url_for("ajustes"))


# ─── Init & run ───────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    seed_all()
    from sqlalchemy import text as _t
    try:
        with db.engine.connect() as _c:
            _c.execute(_t("ALTER TABLE partes_trabajo ADD COLUMN IF NOT EXISTS personas VARCHAR(100)"))
            _c.execute(_t("ALTER TABLE partes_trabajo ADD COLUMN IF NOT EXISTS portes_texto VARCHAR(300)"))
            _c.execute(_t("ALTER TABLE partes_trabajo ADD COLUMN IF NOT EXISTS total_portes FLOAT DEFAULT 0"))
            _c.execute(_t("ALTER TABLE partes_trabajo ADD COLUMN IF NOT EXISTS gasto_gasoil FLOAT DEFAULT 0"))
            _c.execute(_t("ALTER TABLE partes_trabajo ADD COLUMN IF NOT EXISTS gasto_furgoneta FLOAT DEFAULT 0"))
            _c.execute(_t("ALTER TABLE partes_trabajo ADD COLUMN IF NOT EXISTS gasto_empleado FLOAT DEFAULT 60"))
            _c.execute(_t("ALTER TABLE facturas ADD COLUMN IF NOT EXISTS fecha_envio DATE"))
            _c.execute(_t("ALTER TABLE facturas ALTER COLUMN estado SET DEFAULT 'pendiente'"))
            _c.commit()
    except Exception as _e:
        print(f"Migration: {_e}")
