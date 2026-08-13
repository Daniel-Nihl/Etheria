import os
import re
import hashlib
from functools import wraps
from uuid import uuid4
from flask import (Flask, render_template, request, jsonify, redirect, session, flash, url_for, get_flashed_messages,)
from sqlalchemy.orm import joinedload
from werkzeug.utils import secure_filename
from db import db
from models import (Usuario, Media, PeliculaDetalle, SerieDetalle, Temporada, Episodio, Lista, Visto,)

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "clave_secreta"
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
db_folder = os.path.join(BASE_DIR, "database")
upload_folder = os.path.join(BASE_DIR, "static", "img")

os.makedirs(db_folder, exist_ok=True)
os.makedirs(upload_folder, exist_ok=True)

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{os.path.join(db_folder, 'media.db')}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = upload_folder
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}

db.init_app(app)


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        usuario_id = session.get("usuario_id")

        if not usuario_id:
            return redirect(url_for("index"))

        usuario = Usuario.query.get(usuario_id)
        if not usuario or not usuario.is_admin:
            return redirect(url_for("home"))

        return view(*args, **kwargs)

    return wrapped_view


def allowed_image(filename):
    return (
            bool(filename)
            and "." in filename
            and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS
    )


def _file_hash(file_obj):
    """Calcula un SHA-256 sin dejar el puntero del archivo desplazado."""
    original_position = file_obj.tell()
    file_obj.seek(0)

    hasher = hashlib.sha256()

    while True:
        chunk = file_obj.read(1024 * 1024)
        if not chunk:
            break
        hasher.update(chunk)

    file_obj.seek(original_position)
    return hasher.hexdigest()


def _find_existing_image(file_storage, extension, image_hash):
    """
    Busca una imagen idéntica ya almacenada.

    Solo se reutiliza un archivo con la misma extensión y el mismo
    contenido binario para evitar problemas de MIME/extensión.
    """
    upload_folder_path = app.config["UPLOAD_FOLDER"]

    try:
        file_size = os.fstat(file_storage.stream.fileno()).st_size
    except (AttributeError, OSError):
        current_position = file_storage.stream.tell()
        file_storage.stream.seek(0, os.SEEK_END)
        file_size = file_storage.stream.tell()
        file_storage.stream.seek(current_position)

    for filename in os.listdir(upload_folder_path):
        path = os.path.join(upload_folder_path, filename)

        if not os.path.isfile(path):
            continue

        existing_extension = os.path.splitext(filename)[1].lower().lstrip(".")
        if existing_extension != extension:
            continue

        try:
            if os.path.getsize(path) != file_size:
                continue

            with open(path, "rb") as existing_file:
                if _file_hash(existing_file) == image_hash:
                    return filename
        except OSError:
            continue

    return None


def save_image(file_storage):
    """
    Guarda una imagen solo si no existe ya una copia idéntica.

    Si el mismo archivo ya está almacenado, devuelve el nombre del archivo
    existente en lugar de crear una segunda copia física.
    """
    if not file_storage or not file_storage.filename:
        return None

    if not allowed_image(file_storage.filename):
        raise ValueError("Formato de imagen no permitido.")

    original_name = secure_filename(file_storage.filename)
    extension = original_name.rsplit(".", 1)[1].lower()

    image_hash = _file_hash(file_storage.stream)

    existing_filename = _find_existing_image(
        file_storage,
        extension,
        image_hash,
    )

    if existing_filename:
        file_storage.stream.seek(0)
        return existing_filename

    unique_name = f"{uuid4().hex}.{extension}"
    file_storage.stream.seek(0)
    file_storage.save(
        os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
    )

    return unique_name


def _image_is_referenced(filename):
    """
    Comprueba si una imagen sigue siendo utilizada por algún registro.
    Se revisan Media, Temporada y Episodio porque cualquiera de ellos
    puede reutilizar el mismo archivo físico.
    """
    if not filename:
        return False

    return (
            Media.query.filter_by(imagen=filename).first() is not None
            or Temporada.query.filter_by(imagen=filename).first() is not None
            or Episodio.query.filter_by(imagen=filename).first() is not None
    )


def delete_image(filename):
    """
    Elimina físicamente una imagen solo cuando ningún registro la utiliza.
    """
    if not filename or _image_is_referenced(filename):
        return

    path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    if os.path.isfile(path):
        try:
            os.remove(path)
        except OSError:
            pass


def ensure_default_admin():
    """Create the initial administrator only when no admin exists yet."""
    if not Usuario.query.filter_by(is_admin=True).first():
        admin = Usuario(
            nombre="admin",
            password="1234",
            is_admin=True,
        )
        db.session.add(admin)
        db.session.commit()


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "GET":
        get_flashed_messages()
        session.pop("flashes", None)

    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        password = request.form.get("password", "")

        usuario = Usuario.query.filter_by(nombre=nombre).first()

        if usuario and usuario.check_password(password):
            session["usuario_id"] = usuario.id
            flash("Inicio de sesión exitoso", "success")

            if usuario.is_admin:
                return redirect(url_for("admin_home"))

            return redirect(url_for("home"))

        flash("Usuario o contraseña incorrectos", "danger")

    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nombre = request.form.get("nombre", "").strip()
        password = request.form.get("password", "")

        if Usuario.query.filter_by(nombre=nombre).first():
            flash("El nombre de usuario ya existe", "danger")
            return render_template("register.html", nombre=nombre)

        if len(password) < 6 or not re.search(r"[A-Z]", password):
            flash(
                "La contraseña debe tener al menos 6 caracteres "
                "y al menos una letra mayúscula",
                "danger",
            )
            return render_template("register.html", nombre=nombre)

        nuevo_usuario = Usuario(
            nombre=nombre,
            password=password,
            is_admin=False,
        )
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

    peliculas = (
        Media.query
        .options(joinedload(Media.pelicula_detalle))
        .filter_by(tipo="pelicula", oculto=False)
        .all()
    )

    series = (
        Media.query
        .options(joinedload(Media.serie_detalle))
        .filter_by(tipo="serie", oculto=False)
        .all()
    )

    dramas = Media.query.filter_by(oculto=False, genero="Drama").all()
    animacion = Media.query.filter_by(oculto=False, genero="Animación").all()
    romance = Media.query.filter_by(oculto=False, genero="Romance").all()

    return render_template(
        "home.html",
        usuario=usuario,
        peliculas=peliculas,
        series=series,
        dramas=dramas,
        animacion=animacion,
        romance=romance,
    )


@app.route("/admin/home")
@admin_required
def admin_home():
    usuario = Usuario.query.get(session["usuario_id"])

    peliculas = Media.query.filter_by(tipo="pelicula").all()
    series = Media.query.filter_by(tipo="serie").all()
    dramas = Media.query.filter_by(genero="Drama").all()
    animacion = Media.query.filter_by(genero="Animación").all()
    romance = Media.query.filter_by(genero="Romance").all()

    return render_template(
        "admin_home.html",
        usuario=usuario,
        peliculas=peliculas,
        series=series,
        dramas=dramas,
        animacion=animacion,
        romance=romance,
    )


@app.route("/admin/media")
@admin_required
def admin_media():
    peliculas = (
        Media.query
        .filter_by(tipo="pelicula")
        .order_by(Media.titulo.asc())
        .all()
    )
    series = (
        Media.query
        .options(joinedload(Media.serie_detalle).joinedload(SerieDetalle.temporadas))
        .filter_by(tipo="serie")
        .order_by(Media.titulo.asc())
        .all()
    )

    return render_template(
        "admin_media.html",
        peliculas=peliculas,
        series=series,
    )


@app.route("/admin/media/crear/pelicula", methods=["POST"])
@admin_required
def crear_pelicula():
    titulo = request.form.get("titulo", "").strip()
    genero = request.form.get("genero", "").strip() or None
    descripcion = request.form.get("descripcion", "").strip() or None
    anio_raw = request.form.get("anio", "").strip()
    duracion_raw = request.form.get("duracion", "").strip()
    director = request.form.get("director", "").strip() or None
    imagen = request.files.get("imagen")

    if not titulo:
        flash("El título de la película es obligatorio.", "danger")
        return redirect(url_for("admin_media"))

    if Media.query.filter_by(titulo=titulo).first():
        flash("Ya existe una media con ese título.", "danger")
        return redirect(url_for("admin_media"))

    if not imagen or not imagen.filename:
        flash("La miniatura de la película es obligatoria.", "danger")
        return redirect(url_for("admin_media"))

    try:
        anio = int(anio_raw) if anio_raw else None
        duracion = int(duracion_raw) if duracion_raw else None

        if anio is not None and anio < 0:
            raise ValueError
        if duracion is not None and duracion < 0:
            raise ValueError

        nombre_imagen = save_image(imagen)
    except ValueError as exc:
        flash(str(exc) if str(exc) else "Los valores numéricos no son válidos.", "danger")
        return redirect(url_for("admin_media"))

    media = Media(
        titulo=titulo,
        genero=genero,
        anio=anio,
        tipo="pelicula",
        imagen=nombre_imagen,
        descripcion=descripcion,
        oculto=False,
    )

    detalle = PeliculaDetalle(
        media=media,
        duracion=duracion,
        director=director,
    )

    db.session.add(media)
    db.session.add(detalle)
    db.session.commit()

    flash(f"Película '{titulo}' añadida correctamente.", "success")
    return redirect(url_for("admin_media"))


@app.route("/admin/media/crear/serie", methods=["POST"])
@admin_required
def crear_serie():
    titulo = request.form.get("titulo", "").strip()
    genero = request.form.get("genero", "").strip() or None
    descripcion = request.form.get("descripcion", "").strip() or None
    anio_raw = request.form.get("anio", "").strip()
    showrunner = request.form.get("showrunner", "").strip() or None
    imagen = request.files.get("imagen")

    if not titulo:
        flash("El título de la serie es obligatorio.", "danger")
        return redirect(url_for("admin_media"))

    if Media.query.filter_by(titulo=titulo).first():
        flash("Ya existe una media con ese título.", "danger")
        return redirect(url_for("admin_media"))

    if not imagen or not imagen.filename:
        flash("La miniatura de la serie es obligatoria.", "danger")
        return redirect(url_for("admin_media"))

    try:
        anio = int(anio_raw) if anio_raw else None
        if anio is not None and anio < 0:
            raise ValueError
        nombre_imagen = save_image(imagen)
    except ValueError as exc:
        flash(str(exc) if str(exc) else "El año no es válido.", "danger")
        return redirect(url_for("admin_media"))

    media = Media(
        titulo=titulo,
        genero=genero,
        anio=anio,
        tipo="serie",
        imagen=nombre_imagen,
        descripcion=descripcion,
        oculto=False,
    )

    detalle = SerieDetalle(
        media=media,
        showrunner=showrunner,
    )

    db.session.add(media)
    db.session.add(detalle)
    db.session.commit()

    flash(f"Serie '{titulo}' añadida correctamente.", "success")
    return redirect(url_for("admin_serie", media_id=media.id))


@app.route("/admin/media/<int:media_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_media(media_id):
    media = Media.query.get(media_id)

    if not media:
        flash("Media no encontrada.", "danger")
        return redirect(url_for("admin_media"))

    titulo = media.titulo
    imagen_principal = media.imagen

    # Guardar referencias de imágenes secundarias antes de eliminar relaciones.
    imagenes_temporadas = []
    imagenes_episodios = []

    if media.serie_detalle:
        for temporada in media.serie_detalle.temporadas:
            if temporada.imagen:
                imagenes_temporadas.append(temporada.imagen)
            for episodio in temporada.episodios:
                if episodio.imagen:
                    imagenes_episodios.append(episodio.imagen)

    db.session.delete(media)
    db.session.commit()

    delete_image(imagen_principal)
    for imagen in imagenes_temporadas:
        delete_image(imagen)
    for imagen in imagenes_episodios:
        delete_image(imagen)

    flash(f"'{titulo}' eliminada correctamente.", "success")
    return redirect(url_for("admin_media"))


@app.route("/admin/series/<int:media_id>")
@admin_required
def admin_serie(media_id):
    media = Media.query.get(media_id)

    if not media or media.tipo != "serie" or not media.serie_detalle:
        flash("Serie no encontrada.", "danger")
        return redirect(url_for("admin_media"))

    serie = media.serie_detalle
    return render_template("admin_serie.html", media=media, serie=serie)


@app.route("/admin/series/<int:media_id>/temporadas/crear", methods=["POST"])
@admin_required
def crear_temporada(media_id):
    media = Media.query.get(media_id)

    if not media or media.tipo != "serie" or not media.serie_detalle:
        flash("Serie no encontrada.", "danger")
        return redirect(url_for("admin_media"))

    try:
        numero = int(request.form.get("numero", "").strip())
        if numero < 1:
            raise ValueError
    except ValueError:
        flash("El número de temporada debe ser un entero mayor que 0.", "danger")
        return redirect(url_for("admin_serie", media_id=media_id))

    if any(t.numero == numero for t in media.serie_detalle.temporadas):
        flash("Esa temporada ya existe.", "danger")
        return redirect(url_for("admin_serie", media_id=media_id))

    titulo = request.form.get("titulo", "").strip() or None
    descripcion = request.form.get("descripcion", "").strip() or None

    try:
        imagen = save_image(request.files.get("imagen"))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin_serie", media_id=media_id))

    temporada = Temporada(
        serie=media.serie_detalle,
        numero=numero,
        titulo=titulo,
        descripcion=descripcion,
        imagen=imagen,
    )

    db.session.add(temporada)
    db.session.commit()

    flash(f"Temporada {numero} añadida correctamente.", "success")
    return redirect(url_for("admin_serie", media_id=media_id))


@app.route("/admin/temporadas/<int:temporada_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_temporada(temporada_id):
    temporada = Temporada.query.get(temporada_id)

    if not temporada:
        flash("Temporada no encontrada.", "danger")
        return redirect(url_for("admin_media"))

    media_id = temporada.serie.media_id
    imagen_temporada = temporada.imagen
    imagenes_episodios = [
        episodio.imagen
        for episodio in temporada.episodios
        if episodio.imagen
    ]

    db.session.delete(temporada)
    db.session.commit()

    delete_image(imagen_temporada)
    for imagen in imagenes_episodios:
        delete_image(imagen)

    flash("Temporada eliminada correctamente.", "success")
    return redirect(url_for("admin_serie", media_id=media_id))


@app.route("/admin/temporadas/<int:temporada_id>/episodios/crear", methods=["POST"])
@admin_required
def crear_episodio(temporada_id):
    temporada = Temporada.query.get(temporada_id)

    if not temporada:
        flash("Temporada no encontrada.", "danger")
        return redirect(url_for("admin_media"))

    try:
        numero = int(request.form.get("numero", "").strip())
        if numero < 1:
            raise ValueError
    except ValueError:
        flash("El número de episodio debe ser un entero mayor que 0.", "danger")
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    if any(e.numero == numero for e in temporada.episodios):
        flash("Ese episodio ya existe en la temporada.", "danger")
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    titulo = request.form.get("titulo", "").strip()
    descripcion = request.form.get("descripcion", "").strip() or None

    if not titulo:
        flash("El título del episodio es obligatorio.", "danger")
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    try:
        imagen = save_image(request.files.get("imagen"))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    episodio = Episodio(
        temporada=temporada,
        numero=numero,
        titulo=titulo,
        descripcion=descripcion,
        imagen=imagen,
    )

    db.session.add(episodio)
    db.session.commit()

    flash(f"Episodio {numero} añadido correctamente.", "success")
    return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))


@app.route("/admin/temporadas/<int:temporada_id>/episodios/crear-muchos", methods=["POST"])
@admin_required
def crear_muchos_episodios(temporada_id):
    temporada = Temporada.query.get(temporada_id)

    if not temporada:
        flash("Temporada no encontrada.", "danger")
        return redirect(url_for("admin_media"))

    try:
        cantidad = int(request.form.get("cantidad", "").strip())
        if cantidad < 1:
            raise ValueError
    except ValueError:
        flash("La cantidad de episodios debe ser un entero mayor que 0.", "danger")
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    if cantidad > 1000:
        flash("No se pueden crear más de 1000 episodios de una vez.", "danger")
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    episodios_existentes = {episodio.numero for episodio in temporada.episodios}
    ultimo_numero = max(episodios_existentes, default=0)

    imagen_default = temporada.imagen

    # Una miniatura subida aquí tiene prioridad sobre la de la temporada.
    imagen_subida = request.files.get("imagen_default")
    if imagen_subida and imagen_subida.filename:
        try:
            imagen_default = save_image(imagen_subida)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    if not imagen_default:
        flash(
            "La temporada no tiene miniatura. Sube una miniatura por defecto para los episodios.",
            "danger",
        )
        return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))

    episodios = []
    numero = ultimo_numero + 1

    while len(episodios) < cantidad:
        if numero not in episodios_existentes:
            episodios.append(
                Episodio(
                    temporada=temporada,
                    numero=numero,
                    titulo=f"Episodio {numero}",
                    descripcion=None,
                    imagen=imagen_default,
                )
            )
        numero += 1

    db.session.add_all(episodios)
    db.session.commit()

    inicio = episodios[0].numero
    fin = episodios[-1].numero

    flash(
        f"Se han creado {cantidad} episodios ({inicio}-{fin}) correctamente.",
        "success",
    )
    return redirect(url_for("admin_serie", media_id=temporada.serie.media_id))


@app.route("/admin/episodios/<int:episodio_id>/editar", methods=["POST"])
@admin_required
def editar_episodio(episodio_id):
    episodio = Episodio.query.get(episodio_id)

    if not episodio:
        flash("Episodio no encontrado.", "danger")
        return redirect(url_for("admin_media"))

    titulo = request.form.get("titulo", "").strip()
    descripcion = request.form.get("descripcion", "").strip() or None

    if not titulo:
        flash("El título del episodio es obligatorio.", "danger")
        return redirect(
            url_for("admin_serie", media_id=episodio.temporada.serie.media_id)
        )

    imagen_anterior = episodio.imagen
    imagen_nueva = imagen_anterior

    imagen_subida = request.files.get("imagen")
    if imagen_subida and imagen_subida.filename:
        try:
            imagen_nueva = save_image(imagen_subida)
        except ValueError as exc:
            flash(str(exc), "danger")
            return redirect(
                url_for("admin_serie", media_id=episodio.temporada.serie.media_id)
            )

    episodio.titulo = titulo
    episodio.descripcion = descripcion
    episodio.imagen = imagen_nueva

    db.session.commit()

    if imagen_nueva != imagen_anterior:
        delete_image(imagen_anterior)

    flash(f"Episodio {episodio.numero} actualizado correctamente.", "success")
    return redirect(
        url_for("admin_serie", media_id=episodio.temporada.serie.media_id)
    )


@app.route("/admin/episodios/<int:episodio_id>/eliminar", methods=["POST"])
@admin_required
def eliminar_episodio(episodio_id):
    episodio = Episodio.query.get(episodio_id)

    if not episodio:
        flash("Episodio no encontrado.", "danger")
        return redirect(url_for("admin_media"))

    media_id = episodio.temporada.serie.media_id
    imagen = episodio.imagen

    db.session.delete(episodio)
    db.session.commit()

    delete_image(imagen)

    flash("Episodio eliminado correctamente.", "success")
    return redirect(url_for("admin_serie", media_id=media_id))


@app.route("/admin_buscar", methods=["GET"])
@admin_required
def admin_buscar():
    usuario = Usuario.query.get(session["usuario_id"])
    query = request.args.get("q", "").strip()

    if query:
        resultados = Media.query.filter(Media.titulo.ilike(f"%{query}%")).all()
    else:
        resultados = []

    return render_template(
        "admin_buscar.html",
        usuario=usuario,
        resultados=resultados,
        query=query,
    )


@app.route("/api/series/<int:media_id>")
def api_serie(media_id):
    usuario_id = session.get("usuario_id")
    usuario = Usuario.query.get(usuario_id) if usuario_id else None
    media = Media.query.get(media_id)

    if not media or media.tipo != "serie" or not media.serie_detalle:
        return jsonify({"success": False, "error": "Serie no encontrada"}), 404

    if not usuario or not usuario.is_admin:
        if media.oculto:
            return jsonify({"success": False, "error": "Serie no encontrada"}), 404

    data = {
        "id": media.id,
        "titulo": media.titulo,
        "descripcion": media.descripcion,
        "temporadas": [],
    }

    for temporada in media.serie_detalle.temporadas:
        temporada_data = {
            "id": temporada.id,
            "numero": temporada.numero,
            "titulo": temporada.titulo,
            "descripcion": temporada.descripcion,
            "imagen": temporada.imagen,
            "episodios": [],
        }

        for episodio in temporada.episodios:
            temporada_data["episodios"].append({
                "id": episodio.id,
                "numero": episodio.numero,
                "titulo": episodio.titulo,
                "descripcion": episodio.descripcion,
                "imagen": episodio.imagen,
            })

        data["temporadas"].append(temporada_data)

    return jsonify(data)


@app.route("/api/buscar_media")
def buscar_media():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify([])

    usuario_id = session.get("usuario_id")
    usuario = Usuario.query.get(usuario_id) if usuario_id else None
    is_admin = usuario.is_admin if usuario else False

    filtros = [Media.titulo.ilike(f"%{q}%")]
    if not is_admin:
        filtros.append(Media.oculto == False)

    resultados = Media.query.filter(*filtros).all()
    data = []

    for m in resultados:
        item = {
            "id": m.id,
            "titulo": m.titulo,
            "imagen": m.imagen,
            "anio": m.anio,
            "genero": m.genero,
            "tipo": m.tipo,
            "descripcion": m.descripcion,
            "duracion": m.pelicula_detalle.duracion if m.pelicula_detalle else None,
            "director": m.pelicula_detalle.director if m.pelicula_detalle else None,
            "showrunner": m.serie_detalle.showrunner if m.serie_detalle else None,
            "temporadas": len(m.serie_detalle.temporadas) if m.serie_detalle else 0,
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

    return render_template(
        "peliculas.html",
        peliculas=peliculas,
        drama=drama,
        animacion=animacion,
        romance=romance,
    )


@app.route("/series")
def ver_series():
    series = Media.query.filter_by(oculto=False, tipo="serie").all()
    dramas = Media.query.filter_by(tipo="serie", oculto=False, genero="Drama").all()
    animacion = Media.query.filter_by(tipo="serie", oculto=False, genero="Animación").all()
    romance = Media.query.filter_by(tipo="serie", oculto=False, genero="Romance").all()

    return render_template(
        "series.html",
        series=series,
        dramas=dramas,
        animacion=animacion,
        romance=romance,
    )


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

    if usuario and usuario.is_admin:
        return redirect(url_for("admin_buscar", q=request.args.get("q", "")))

    query = request.args.get("q", "").strip()

    if not query:
        return render_template(
            "buscar.html",
            usuario=usuario,
            resultados=[],
            query=query,
        )

    resultados = Media.query.filter(
        Media.titulo.ilike(f"%{query}%"),
        Media.oculto == False,
    ).all()

    return render_template(
        "buscar.html",
        usuario=usuario,
        resultados=resultados,
        query=query,
    )


@app.route("/usuarios")
@admin_required
def ver_usuarios():
    usuarios = Usuario.query.all()
    return render_template("usuarios.html", usuarios=usuarios)


@app.route("/usuarios/eliminar/<int:user_id>", methods=["POST"])
@admin_required
def eliminar_usuario(user_id):
    usuario = Usuario.query.get(user_id)

    if not usuario:
        return jsonify({"success": False, "error": "Usuario no encontrado"})

    if usuario.is_admin:
        return jsonify({"success": False, "error": "No se puede eliminar al admin"})

    db.session.delete(usuario)
    db.session.commit()
    return jsonify({"success": True})


@app.route("/ocultar_media/<int:media_id>", methods=["POST"])
@admin_required
def ocultar_media(media_id):
    media = Media.query.get(media_id)

    if not media:
        return jsonify({"success": False, "error": "No encontrado"}), 404

    media.oculto = not media.oculto
    db.session.commit()

    return jsonify({
        "success": True,
        "oculto": media.oculto,
    })


@app.route("/en_lista/<titulo>")
def en_lista(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"en_lista": False})

    existe = Lista.query.filter_by(
        usuario_id=usuario_id,
    ).join(Lista.media).filter(Media.titulo == titulo).first()

    return jsonify({"en_lista": bool(existe)})


@app.route("/toggle_lista/<titulo>", methods=["POST"])
def toggle_lista(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"success": False, "error": "No autenticado"}), 403

    media = Media.query.filter_by(titulo=titulo).first()
    if not media:
        return jsonify({"success": False, "error": "Media no encontrada"}), 404

    item = Lista.query.filter_by(
        usuario_id=usuario_id,
        media_id=media.id,
    ).first()

    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"en_lista": False})

    nuevo = Lista(
        usuario=Usuario.query.get(usuario_id),
        media=media,
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({"en_lista": True})


@app.route("/toggle_visto/<titulo>", methods=["POST"])
def toggle_visto(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"success": False, "error": "No autenticado"}), 403

    media = Media.query.filter_by(titulo=titulo).first()
    if not media:
        return jsonify({"success": False, "error": "Media no encontrada"}), 404

    item = Visto.query.filter_by(
        usuario_id=usuario_id,
        media_id=media.id,
    ).first()

    if item:
        db.session.delete(item)
        db.session.commit()
        return jsonify({"visto": False})

    nuevo = Visto(
        usuario=Usuario.query.get(usuario_id),
        media=media,
    )
    db.session.add(nuevo)
    db.session.commit()
    return jsonify({"visto": True})


@app.route("/en_visto/<titulo>")
def en_visto(titulo):
    usuario_id = session.get("usuario_id")
    if not usuario_id:
        return jsonify({"visto": False})

    existe = Visto.query.filter_by(
        usuario_id=usuario_id,
    ).join(Visto.media).filter(Media.titulo == titulo).first()

    return jsonify({"visto": bool(existe)})


with app.app_context():
    db.create_all()
    ensure_default_admin()

if __name__ == "__main__":
    app.run(debug=True)