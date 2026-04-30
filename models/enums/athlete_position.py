from enum import Enum


class AthletePosition(str, Enum):
    CENTRAL = "Central"
    LEVANTADOR = "Levantador"
    LIBERO = "Líbero"
    OPOSTO = "Oposto"
    PONTEIRO = "Ponteiro"
