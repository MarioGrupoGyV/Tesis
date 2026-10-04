from typing import Literal
from pydantic import Field
from app.schemas.s1 import ContractModel


class ProcessingOperation(ContractModel):
    available: bool
    reason: str | None


class ProcessingOperations(ContractModel):
    compare: ProcessingOperation
    register_: ProcessingOperation = Field(alias='register')
    activate: ProcessingOperation
    predict: ProcessingOperation
    read_students: ProcessingOperation
    read_models: ProcessingOperation
    read_alerts: ProcessingOperation
    write_followup: ProcessingOperation
    sync_alerts: ProcessingOperation
    read_reports: ProcessingOperation
    export_reports: ProcessingOperation

    # Alias contractual; no palabra reservada en Python.
    import_: ProcessingOperation = Field(alias='import')


class ProcessingStatus(ContractModel):
    scope: Literal['SYNTHETIC_STUDY']
    notice: str
    institutional_ready: Literal[False]
    synthetic_ready: bool
    operations: ProcessingOperations
