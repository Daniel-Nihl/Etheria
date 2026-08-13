import os
from flask import Flask, render_template, request, jsonify, redirect, session, flash, url_for, get_flashed_messages
from db import db
from models import Usuario, Media, PeliculaDetalle, SerieDetalle, Lista, Visto
from sqlalchemy.orm import joinedload
import re

app = Flask(__name__)
app.secret_key = "clave_secreta"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_folder = os.path.join(BASE_DIR, "database")
os.makedirs(db_folder, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(db_folder, 'media.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

def seed_data():
    if Usuario.query.count() == 0:
        admin = Usuario(nombre="admin", password="1234", is_admin=True)
        db.session.add(admin)
        usuario1 = Usuario(nombre="1", password="1", is_admin=False)
        db.session.add(usuario1)

    if Media.query.count() == 0:
        media_items = [
            Media(titulo="Into The Spiderverse", genero="Animación", anio=2018, tipo="pelicula", imagen="Into_The_Spiderverse.jpg"),
            Media(titulo="Crazy, Stupid, Love", genero="Romance", anio=2011, tipo="pelicula", imagen="crazy_stupid_love.jpg"),
            Media(titulo="Parásitos", genero="Drama", anio=2019, tipo="pelicula", imagen="Parásitos.jpg"),
            Media(titulo="Antes del Amanecer", genero="Romance", anio=1995, tipo="pelicula", imagen="Antes_Del_Amanecer.jpg"),
            Media(titulo="Oppenheimer", genero="Drama", anio=2023, tipo="pelicula", imagen="Oppenheimer.jpg"),
            Media(titulo="Shrek", genero="Animación", anio=2001, tipo="pelicula", imagen="Shrek.jpg"),

            Media(titulo="Padre de familia", genero="Animación", anio=1999, tipo="serie", imagen="padre_de_familia.jpg", temporadas=2),
            Media(titulo="Breaking Bad", genero="Drama", anio=2008, tipo="serie", imagen="Breaking_Bad.jpg", temporadas=2),
            Media(titulo="Outlander", genero="Romance", anio=2014, tipo="serie", imagen="Outlander.jpg", temporadas=2),
            Media(titulo="Midnight Gospel", genero="Animación", anio=2020, tipo="serie", imagen="Midnight_Gospel.jpg", temporadas=2),
            Media(titulo="Fleabag", genero="Romance", anio=2016, tipo="serie", imagen="Fleabag.jpg", temporadas=2),
            Media(titulo="House MD", genero="Drama", anio=2004, tipo="serie", imagen="House_MD.jpg", temporadas=2),
        ]
        db.session.add_all(media_items)
        db.session.commit()

        media_map = {m.titulo: m for m in media_items}

        peliculas_info = [
            ("Into The Spiderverse", 117, "Bob Persichetti"),
            ("Crazy, Stupid, Love", 118, "Glenn Ficarra"),
            ("Parásitos", 132, "Bong Joon-ho"),
            ("Antes del Amanecer", 101, "Richard Linklater"),
            ("Oppenheimer", 180, "Christopher Nolan"),
            ("Shrek", 90, "Andrew Adamson")
        ]
        peliculas_detalle = []
        for titulo, duracion, director in peliculas_info:
            media = media_map.get(titulo)
            detalle = PeliculaDetalle(titulo=titulo, media=media, duracion=duracion, director=director)
            peliculas_detalle.append(detalle)
        db.session.add_all(peliculas_detalle)

        series_info = [
            ("Padre de familia", "Seth MacFarlane", 10),
            ("Breaking Bad", "Vince Gilligan", 13),
            ("Outlander", "Ronald D. Moore", 12),
            ("Midnight Gospel", "Duncan Trussell", 8),
            ("Fleabag", "Phoebe Waller-Bridge", 6),
            ("House MD", "David Shore", 22)
        ]
        series_detalle = []
        for titulo, showrunner, ep_por_temp in series_info:
            media = media_map.get(titulo)
            detalle = SerieDetalle(titulo=titulo, media=media, showrunner=showrunner,
                                   episodios_por_temporada=ep_por_temp)
            series_detalle.append(detalle)
        db.session.add_all(series_detalle)

    db.session.commit()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        get_flashed_messages()
        session.pop("flashes", None)

    if request.method == "POST":
        nombre = request.form.get("nombre")
        password = request.form.get("password")
        usuario = Usuario.query.filter_by(nombre=nombre).first()

        if usuario and usuario.check_password(password):
            session["usuario_id"] = usuario.id
            flash("Inicio de sesión exitoso", "success")
            return redirect(url_for("admin_home") if usuario.is_admin else url_for("home"))
        else:
            flash("Usuario o contraseña incorrectos", "danger")
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form.get("nombre")
        password = request.form.get("password")

        if Usuario.query.filter_by(nombre=nombre).first():
            flash("El nombre de usuario ya existe", "danger")
            return render_template("register.html", nombre=nombre)

        if len(password) < 6 or not re.search(r"[A-Z]", password):
            flash("La contraseña debe tener al menos 6 caracteres y al menos una letra mayúscula", "danger")
            return render_template("register.html", nombre=nombre)

        nuevo_usuario = Usuario(nombre=nombre, password=password, is_admin=False)
        db.session.add(nuevo_usuario)
        db.session.commit()
        flash("Registro exitoso", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/logout", methods=["GET", "POST"])
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/home")
def home():
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario = Usuario.query.get(session["usuario_id"])
    if not usuario:
        session.pop("usuario_id", None)
        return redirect(url_for("index"))

    if usuario.is_admin:
        return redirect(url_for("admin_home"))

    peliculas = Media.query.options(joinedload(Media.pelicula_detalle))\
        .filter_by(tipo="pelicula", oculto=False).all()
    series = Media.query.options(joinedload(Media.serie_detalle)) \
        .filter_by(tipo="serie", oculto=False).all()
    dramas = Media.query.filter_by(oculto=False, genero="Drama").all()
    animacion = Media.query.filter_by(oculto=False, genero="Animación").all()
    romance = Media.query.filter_by(oculto=False, genero="Romance").all()

    return render_template("home.html", usuario=usuario, peliculas=peliculas, series=series,
                           dramas=dramas, animacion=animacion, romance=romance)

@app.route("/admin/home")
def admin_home():
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario = Usuario.query.get(session["usuario_id"])
    if not usuario or not usuario.is_admin:
        return redirect(url_for("home"))

    peliculas = Media.query.filter_by(tipo="pelicula").all()
    series = Media.query.filter_by(tipo="serie").all()
    dramas = Media.query.filter_by(genero="Drama").all()
    animacion = Media.query.filter_by(genero="Animación").all()
    romance = Media.query.filter_by(genero="Romance").all()

    return render_template(
        "admin_home.html", usuario=usuario, peliculas=peliculas, series=series, dramas=dramas, animacion=animacion, romance=romance)


@app.route("/admin_peliculas")
def admin_peliculas():
    peliculas = Media.query.filter_by(tipo="pelicula").all()
    return render_template("admin_peliculas.html", peliculas=peliculas)


@app.route("/admin_series")
def admin_series():
    series = Media.query.filter_by(tipo="serie").all()
    return render_template("admin_series.html", series=series)


@app.route("/admin_buscar", methods=["GET"])
def admin_buscar():
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario = Usuario.query.get(session["usuario_id"])
    if not usuario or not usuario.is_admin:
        return redirect(url_for("home"))

    query = request.args.get("q", "")
    if query:
        resultados = Media.query.filter(Media.titulo.ilike(f"%{query}%")).all()
    else:
        resultados = []

    return render_template("admin_buscar.html", usuario=usuario, resultados=resultados, query=query)


@app.route("/api/buscar_media")
def buscar_media():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    usuario_id = session.get("usuario_id")
    usuario = Usuario.query.get(usuario_id) if usuario_id else None
    is_admin = usuario.is_admin if usuario else False

    if is_admin:
        resultados = Media.query.filter(Media.titulo.ilike(f"%{q}%")).all()
    else:
        resultados = Media.query.filter(
            Media.titulo.ilike(f"%{q}%"),
            Media.oculto == False
        ).all()

    data = []
    for m in resultados:
        item = {
            "id": m.id,
            "titulo": m.titulo,
            "imagen": m.imagen,
            "anio": m.anio,
            "genero": m.genero,
            "tipo": "serie" if m.serie_detalle else "pelicula",
            "duracion": m.pelicula_detalle.duracion if m.pelicula_detalle else None,
            "director": m.pelicula_detalle.director if m.pelicula_detalle else None,
            "showrunner": m.serie_detalle.showrunner if m.serie_detalle else None,
            "temporadas": m.serie_detalle.temporadas if m.serie_detalle else None,
        }

        if is_admin:
            item["oculto"] = m.oculto

        data.append(item)

    return jsonify(data)


@app.route("/peliculas")
def ver_peliculas():
    peliculas = Media.query.filter_by(oculto=False, tipo="pelicula").all()
    drama = Media.query.filter_by(tipo="pelicula", oculto=False, genero="Drama").all()
    animacion = Media.query.filter_by(tipo="pelicula", oculto=False, genero="Animación").all()
    romance = Media.query.filter_by(tipo="pelicula", oculto=False, genero="Romance").all()
    return render_template("peliculas.html", peliculas=peliculas, drama=drama, animacion=animacion, romance=romance)


@app.route("/series")
def ver_series():
    series = Media.query.filter_by(oculto=False, tipo="serie").all()
    dramas = Media.query.filter_by(tipo="serie", oculto=False, genero="Drama").all()
    animacion = Media.query.filter_by(tipo="serie", oculto=False, genero="Animación").all()
    romance = Media.query.filter_by(tipo="serie", oculto=False, genero="Romance").all()
    return render_template("series.html", series=series, dramas=dramas, animacion=animacion, romance=romance)


@app.route("/lista")
def ver_lista():
    if "usuario_id" not in session:
        return redirect(url_for("login"))

    usuario_id = session["usuario_id"]
    lista = Lista.query.filter_by(usuario_id=usuario_id).all()

    lista = [item for item in lista if not item.oculto]

    return render_template("lista.html", lista=lista)


@app.route("/visto")
def ver_visto():
    if "usuario_id" not in session:
        return redirect(url_for("login"))
    usuario_id = session["usuario_id"]
    vistos = Visto.query.filter_by(usuario_id=usuario_id).all()
    vistos = [item for item in vistos if not item.oculto]
    return render_template("visto.html", vistos=vistos)


@app.route("/buscar")
def buscar():
    if "usuario_id" not in session:
        return redirect(url_for("index"))

    usuario = Usuario.query.get(session["usuario_id"])
    query = request.args.get("q", "").strip()

    if not query:
        return render_template("buscar.html", usuario=usuario, resultados=[], query=query)

    filtros = [Media.titulo.ilike(f"%{query}%")]
    # Solo los no-admin filtran por oculto
    if not usuario.is_admin:
        filtros.append(Media.oculto == False)

    resultados = Media.query.filter(*filtros).all()

    return render_template("buscar.html", usuario=usuario, resultados=resultados, query=query)


@app.route("/usuarios")
def ver_usuarios():
    usuarios = Usuario.query.all()
    return render_template("usuarios.html", usuarios=usuarios)


@app.route("/usuarios/eliminar/<int:user_id>", methods=["POST"])
def eliminar_usuario(user_id):
    usuario = Usuario.query.get(user_id)
    if not usuario:
        return jsonify({"success": False, "error": "Usuario no encontrado"})
    if usuario.is_admin:
        return jsonify({"success": False, "error": "No se puede eliminar al admin"})

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/ocultar_media/<tipo>/<int:media_id>", methods=["POST"])
def ocultar_media(tipo, media_id):
    model_map = {
        "pelicula": PeliculaDetalle,
        "serie": SerieDetalle,
        "media": Media
    }

    model = model_map.get(tipo)
    if not model:
        return jsonify({"success": False, "error": "Tipo inválido"})

    item = model.query.get(media_id)
    if not item:
        return jsonify({"success": False, "error": "No encontrado"})

    item.oculto = not item.oculto
    db.session.commit()

    if hasattr(item, "media_id") and item.media_id:
        media_item = Media.query.get(item.media_id)
        if media_item:
            media_item.oculto = item.oculto
            db.session.commit()

    return jsonify({"success": True, "oculto": item.oculto})


@app.route("/en_lista/<titulo>")
def en_lista(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"en_lista": False})

    existe = Lista.query.filter_by(usuario_id=usuario_id, titulo=titulo).first()
    return jsonify({"en_lista": bool(existe)})


@app.route("/toggle_lista/<titulo>", methods=["POST"])
def toggle_lista(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"success": False, "error": "No autenticado"}), 403

    item = Lista.query.filter_by(usuario_id=usuario_id, titulo=titulo).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"en_lista": False})
    else:
        media = Media.query.filter_by(titulo=titulo).first()
        if not media:
            return jsonify({"success": False, "error": "Media no encontrada"}), 404

        nuevo = Lista(usuario_id=usuario_id, media=media)
        db.session.add(nuevo)
        db.session.commit()
        return jsonify({"en_lista": True})


@app.route("/toggle_visto/<titulo>", methods=["POST"])
def toggle_visto(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"success": False, "error": "No autenticado"}), 403

    item = Visto.query.filter_by(usuario_id=usuario_id, titulo=titulo).first()
    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"visto": False})
    else:
        media = Media.query.filter_by(titulo=titulo).first()
        if not media:
            return jsonify({"success": False, "error": "Media no encontrada"}), 404

        nuevo = Visto(usuario_id=usuario_id, media=media)
        db.session.add(nuevo)
        db.session.commit()
        return jsonify({"visto": True})


@app.route("/en_visto/<titulo>")
def en_visto(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"visto": False})

    existe = Visto.query.filter_by(usuario_id=usuario_id, titulo=titulo).first()
    return jsonify({"visto": bool(existe)})



with app.app_context():
    db.create_all()
    seed_data()


if __name__ == "__main__":
    app.run(debug=True)
