from db import db
from werkzeug.security import generate_password_hash, check_password_hash


class Usuario(db.Model):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nombre = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, nullable=False, default=False)

    listas = db.relationship(
        "Lista",
        back_populates="usuario",
        cascade="all, delete-orphan"
    )

    vistos = db.relationship(
        "Visto",
        back_populates="usuario",
        cascade="all, delete-orphan"
    )

    def __init__(self, nombre, password, is_admin=False):
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
    descripcion = db.Column(db.Text, nullable=True)
    genero = db.Column(db.String(50), nullable=True)
    anio = db.Column(db.Integer, nullable=True)
    tipo = db.Column(db.String(20), nullable=False)
    imagen = db.Column(db.String(255), nullable=True)
    oculto = db.Column(db.Boolean, nullable=False, default=False)

    pelicula_detalle = db.relationship(
        "PeliculaDetalle",
        back_populates="media",
        uselist=False,
        cascade="all, delete-orphan"
    )

    serie_detalle = db.relationship(
        "SerieDetalle",
        back_populates="media",
        uselist=False,
        cascade="all, delete-orphan"
    )

    listas = db.relationship(
        "Lista",
        back_populates="media",
        cascade="all, delete-orphan"
    )

    vistos = db.relationship(
        "Visto",
        back_populates="media",
        cascade="all, delete-orphan"
    )

    def __init__(
            self,
            titulo,
            genero=None,
            anio=None,
            tipo=None,
            imagen=None,
            descripcion=None,
            oculto=False
    ):
        self.titulo = titulo
        self.genero = genero
        self.anio = anio
        self.tipo = tipo
        self.imagen = imagen
        self.descripcion = descripcion
        self.oculto = oculto

    @property
    def temporadas(self):
        return len(self.serie_detalle.temporadas) if self.serie_detalle else 0


class PeliculaDetalle(db.Model):
    __tablename__ = "peliculas_detalle"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    media_id = db.Column(
        db.Integer,
        db.ForeignKey("media.id"),
        nullable=False,
        unique=True
    )

    duracion = db.Column(db.Integer, nullable=True)
    director = db.Column(db.String(100), nullable=True)

    media = db.relationship(
        "Media",
        back_populates="pelicula_detalle"
    )

    def __init__(self, media, duracion=None, director=None):
        self.media = media
        self.duracion = duracion
        self.director = director


class SerieDetalle(db.Model):
    __tablename__ = "series_detalle"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    media_id = db.Column(
        db.Integer,
        db.ForeignKey("media.id"),
        nullable=False,
        unique=True
    )

    showrunner = db.Column(db.String(100), nullable=True)

    media = db.relationship(
        "Media",
        back_populates="serie_detalle"
    )

    temporadas = db.relationship(
        "Temporada",
        back_populates="serie",
        cascade="all, delete-orphan",
        order_by="Temporada.numero"
    )

    def __init__(self, media, showrunner=None):
        self.media = media
        self.showrunner = showrunner


class Temporada(db.Model):
    __tablename__ = "temporadas"
    __table_args__ = (
        db.UniqueConstraint("serie_id", "numero", name="uq_temporada_serie_numero"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    serie_id = db.Column(
        db.Integer,
        db.ForeignKey("series_detalle.id"),
        nullable=False
    )

    numero = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(100), nullable=True)
    descripcion = db.Column(db.Text, nullable=True)
    imagen = db.Column(db.String(255), nullable=True)

    serie = db.relationship(
        "SerieDetalle",
        back_populates="temporadas"
    )

    episodios = db.relationship(
        "Episodio",
        back_populates="temporada",
        cascade="all, delete-orphan",
        order_by="Episodio.numero"
    )

    def __init__(self, serie, numero, titulo=None, descripcion=None, imagen=None):
        self.serie = serie
        self.numero = numero
        self.titulo = titulo
        self.descripcion = descripcion
        self.imagen = imagen


class Episodio(db.Model):
    __tablename__ = "episodios"
    __table_args__ = (
        db.UniqueConstraint("temporada_id", "numero", name="uq_episodio_temporada_numero"),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    temporada_id = db.Column(
        db.Integer,
        db.ForeignKey("temporadas.id"),
        nullable=False
    )

    numero = db.Column(db.Integer, nullable=False)
    titulo = db.Column(db.String(150), nullable=False)
    descripcion = db.Column(db.Text, nullable=True)
    imagen = db.Column(db.String(255), nullable=True)

    temporada = db.relationship(
        "Temporada",
        back_populates="episodios"
    )

    def __init__(self, temporada, numero, titulo, descripcion=None, imagen=None):
        self.temporada = temporada
        self.numero = numero
        self.titulo = titulo
        self.descripcion = descripcion
        self.imagen = imagen


class Lista(db.Model):
    __tablename__ = "lista"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )
    media_id = db.Column(
        db.Integer,
        db.ForeignKey("media.id"),
        nullable=False
    )

    usuario = db.relationship("Usuario", back_populates="listas")
    media = db.relationship("Media", back_populates="listas")

    def __init__(self, usuario, media):
        self.usuario = usuario
        self.media = media

    @property
    def titulo(self):
        return self.media.titulo if self.media else None

    @property
    def imagen(self):
        return self.media.imagen if self.media else None

    @property
    def oculto(self):
        return self.media.oculto if self.media else False


class Visto(db.Model):
    __tablename__ = "visto"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    usuario_id = db.Column(
        db.Integer,
        db.ForeignKey("usuarios.id"),
        nullable=False
    )
    media_id = db.Column(
        db.Integer,
        db.ForeignKey("media.id"),
        nullable=False
    )

    usuario = db.relationship("Usuario", back_populates="vistos")
    media = db.relationship("Media", back_populates="vistos")

    def __init__(self, usuario, media):
        self.usuario = usuario
        self.media = media

    @property
    def titulo(self):
        return self.media.titulo if self.media else None

    @property
    def imagen(self):
        return self.media.imagen if self.media else None

    @property
    def oculto(self):
        return self.media.oculto if self.media else False