"""API REST compartilhada pela Conexao Coral e pelo app Flutter."""

import math
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/conexao_coral",
)
POOL = ConnectionPool(
    DATABASE_URL,
    kwargs={"row_factory": dict_row, "connect_timeout": 5},
    timeout=5,
    open=False,
)


class ConsuladoInput(BaseModel):
    nome: str = Field(min_length=3, max_length=120)
    cidade: str = Field(min_length=2, max_length=80)
    estado: str = Field(min_length=2, max_length=2)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class Consulado(ConsuladoInput):
    id: int


def initialize_database() -> None:
    with POOL.connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS consulados (
                id BIGSERIAL PRIMARY KEY,
                nome TEXT NOT NULL,
                cidade TEXT NOT NULL,
                estado TEXT NOT NULL,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL
            )
            """
        )
        count = connection.execute("SELECT COUNT(*) AS total FROM consulados").fetchone()["total"]
        if count == 0:
            connection.execute(
                """
                INSERT INTO consulados
                    (nome, cidade, estado, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    "Consulado CoralJampa",
                    "Joao Pessoa",
                    "PB",
                    -7.1195,
                    -34.8450,
                ),
            )


def distance_in_km(
    latitude_a: float,
    longitude_a: float,
    latitude_b: float,
    longitude_b: float,
) -> float:
    """Calcula distância aproximada entre coordenadas usando Haversine."""
    earth_radius_km = 6371.0
    lat_a, lat_b = math.radians(latitude_a), math.radians(latitude_b)
    delta_lat = math.radians(latitude_b - latitude_a)
    delta_lon = math.radians(longitude_b - longitude_a)
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(delta_lon / 2) ** 2
    )
    return 2 * earth_radius_km * math.asin(math.sqrt(haversine))


@asynccontextmanager
async def lifespan(_: FastAPI):
    POOL.open()
    try:
        initialize_database()
        yield
    finally:
        POOL.close()


app = FastAPI(
    title="Conexao Coral API",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/consulados", response_model=list[Consulado])
def list_consulates(
    busca: str | None = Query(default=None, max_length=100),
    latitude: float | None = Query(default=None, ge=-90, le=90),
    longitude: float | None = Query(default=None, ge=-180, le=180),
    raio_km: float | None = Query(default=None, gt=0, le=20000),
) -> list[Consulado]:
    with POOL.connection() as connection:
        rows = connection.execute(
            "SELECT * FROM consulados ORDER BY cidade, nome"
        ).fetchall()

    normalized_search = busca.strip().lower() if busca else None
    result = []
    for row in rows:
        item = dict(row)
        searchable = f"{item['nome']} {item['cidade']} {item['estado']}".lower()
        if normalized_search and normalized_search not in searchable:
            continue
        if (
            raio_km is not None
            and latitude is not None
            and longitude is not None
            and distance_in_km(
                latitude, longitude, item["latitude"], item["longitude"]
            )
            > raio_km
        ):
            continue
        result.append(item)
    return result


@app.post("/consulados", response_model=Consulado, status_code=status.HTTP_201_CREATED)
def create_consulate(payload: ConsuladoInput) -> Consulado:
    values = payload.model_dump()
    values["estado"] = values["estado"].upper()
    with POOL.connection() as connection:
        cursor = connection.execute(
            """
            INSERT INTO consulados
                (nome, cidade, estado, latitude, longitude)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                values["nome"],
                values["cidade"],
                values["estado"],
                values["latitude"],
                values["longitude"],
            ),
        )
        row = cursor.fetchone()
    return row


@app.put("/consulados/{consulado_id}", response_model=Consulado)
def update_consulate(consulado_id: int, payload: ConsuladoInput) -> Consulado:
    values = payload.model_dump()
    values["estado"] = values["estado"].upper()
    values["id"] = consulado_id
    with POOL.connection() as connection:
        cursor = connection.execute(
            """
            UPDATE consulados
            SET nome = %s, cidade = %s, estado = %s,
                latitude = %s, longitude = %s
            WHERE id = %s
            RETURNING *
            """,
            (
                values["nome"],
                values["cidade"],
                values["estado"],
                values["latitude"],
                values["longitude"],
                values["id"],
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Consulado não encontrado")
    return row


@app.delete("/consulados/{consulado_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_consulate(consulado_id: int) -> None:
    with POOL.connection() as connection:
        cursor = connection.execute(
            "DELETE FROM consulados WHERE id = %s", (consulado_id,)
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Consulado não encontrado")
