from db import db
from werkzeug.security import generate_password_hash, check_password_hash


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    def __init__(self, nombre, password, is_admin):
        self.nombre = nombre
        self.set_password(password)
        self.is_admin = is_admin

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Media(db.Model):
    __tablename__ = "media"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(100), nullable=False)
    genero = db.Column(db.String(50))
    anio = db.Column(db.Integer)
    tipo = db.Column(db.String(20), nullable=False)
    imagen = db.Column(db.String(100))
    visto = db.Column(db.Boolean, default=False)
    lista = db.Column(db.Boolean, default=False)
    temporadas = db.Column(db.Integer, nullable=True)
    oculto = db.Column(db.Boolean, default=False)

    pelicula_detalle = db.relationship("PeliculaDetalle", backref="media", uselist=False)
    serie_detalle = db.relationship("SerieDetalle", backref="media", uselist=False)


class PeliculaDetalle(db.Model):
    __tablename__ = "peliculas_detalle"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(100), nullable=False)
    anio = db.Column(db.Integer)
    duracion = db.Column(db.Integer)
    director = db.Column(db.String(100))
    imagen = db.Column(db.String(100))
    oculto = db.Column(db.Boolean, default=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"))

    def __init__(self, titulo, media=None, anio=None, duracion=None, director=None, imagen=None):
        self.titulo = titulo
        self.anio = anio or (media.anio if media else None)
        self.imagen = imagen or (media.imagen if media else None)
        self.duracion = duracion
        self.director = director
        if media:
            self.media = media


class SerieDetalle(db.Model):
    __tablename__ = "series_detalle"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    titulo = db.Column(db.String(100), nullable=False)
    anio = db.Column(db.Integer)
    showrunner = db.Column(db.String(100))
    temporadas = db.Column(db.Integer, default=1)
    episodios_por_temporada = db.Column(db.Integer, default=10)
    imagen = db.Column(db.String(100))
    oculto = db.Column(db.Boolean, default=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"))

    def __init__(self, titulo,media=None, anio=None, showrunner=None, temporadas=None, episodios_por_temporada=None, imagen=None):
        self.titulo = titulo
        self.anio = anio or (media.anio if media else None)
        self.imagen = imagen or (media.imagen if media else None)
        self.temporadas = temporadas or (media.temporadas if media else 1)
        self.showrunner = showrunner
        self.episodios_por_temporada = episodios_por_temporada or 10
        if media:
            self.media = media


class Lista(db.Model):
    __tablename__ = "lista"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    imagen = db.Column(db.String(100), nullable=True)

    media = db.relationship("Media", backref="entradas_lista")

    @property
    def oculto(self):
        return self.media.oculto if self.media else False

    def __init__(self, usuario_id, media=None, titulo=None, imagen=None):
        if media:
            self.usuario_id = usuario_id
            self.media = media
            self.titulo = media.titulo
            self.imagen = media.imagen
        else:
            self.titulo = titulo
            self.imagen = imagen


class Visto(db.Model):
    __tablename__ = "visto"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    media_id = db.Column(db.Integer, db.ForeignKey("media.id"), nullable=False)
    titulo = db.Column(db.String(100), nullable=False)
    imagen = db.Column(db.String(100), nullable=True)

    media = db.relationship("Media", backref="en_visto")

    @property
    def oculto(self):
        return self.media.oculto if self.media else False

    def __init__(self, usuario_id, media=None, titulo=None, imagen=None):
        if media:
            self.usuario_id = usuario_id
            self.media = media
            self.titulo = media.titulo
            self.imagen = media.imagen
        else:
            self.titulo = titulo
            self.imagen = imagen

