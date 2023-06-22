""" Helper script to generate OAS automatically
"""

# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import itertools
from enum import Enum
from typing import Any

from fastapi import FastAPI, status
from models_library.api_schemas_storage import (
    FileMetaDataGet,
    FileUploadCompleteFutureResponse,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    FoldersBody,
    HealthCheck,
    LinkType,
    PresignedLink,
    SoftCopyBody,
    TableSynchronisation,
)
from models_library.app_diagnostics import AppStatusCheck
from models_library.generics import Envelope
from models_library.projects_nodes import NodeID
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, ByteSize
from servicelib.long_running_tasks._models import TaskGet, TaskStatus
from settings_library.s3 import S3Settings
from simcore_service_storage._meta import api_vtag
from simcore_service_storage.models import DatasetMetaData, FileMetaData

TAGS_DATASETS: list[str | Enum] = ["datasets"]
TAGS_FILES: list[str | Enum] = ["files"]
TAGS_HEALTH: list[str | Enum] = ["health"]
TAGS_LOCATIONS: list[str | Enum] = ["locations"]
TAGS_TASKS: list[str | Enum] = ["tasks"]
TAGS_SIMCORE_S3: list[str | Enum] = ["simcore-s3"]


app = FastAPI(
    redoc_url=None,
    description="API definition for simcore-service-storage service",
    version="0.3.0",
    title="simcore-service-storage API",
    contact={"name": "IT'IS Foundation", "email": "support@simcore.io"},
    license_info={
        "name": "MIT",
        "__PLACEHOLDER___KEY_url": "https://github.com/ITISFoundation/osparc-simcore/blob/master/LICENSE",
    },
    servers=[
        {"description": "API server", "url": "/v0"},
        {"description": "Development server", "url": "localhost:8080/v0"},
    ],
    openapi_tags=[
        {"name": x}
        for x in list(
            itertools.chain(
                TAGS_DATASETS,
                TAGS_FILES,
                TAGS_HEALTH,
                TAGS_LOCATIONS,
                TAGS_TASKS,
                TAGS_SIMCORE_S3,
            )
        )
    ],
)


# handlers_datasets.py


@app.get(
    f"/{api_vtag}/locations/{{location_id}}/datasets",
    response_model=Envelope[list[DatasetMetaData]],
    tags=TAGS_DATASETS,
    operation_id="get_datasets_metadata",
    summary="Get datasets metadata",
)
async def get_datasets_metadata(location_id: LocationID, user_id: UserID):
    """Returns the list of dataset meta-datas"""


# handlers_files.py


@app.get(
    f"/{api_vtag}/locations/{{location_id}}/datasets/{{dataset_id}}/metadata",
    response_model=Envelope[list[FileMetaDataGet]],
    tags=TAGS_DATASETS,
    operation_id="get_files_metadata_dataset",
    summary="Get Files Metadata",
)
async def get_files_metadata_dataset(
    location_id: LocationID, dataset_id: str, user_id: UserID, expand_dirs: bool = True
):
    """list of file meta-datas"""


@app.get(
    f"/{api_vtag}/locations",
    response_model=list[DatasetMetaData],
    tags=TAGS_LOCATIONS,
    operation_id="get_storage_locations",
    summary="Get available storage locations",
)
async def get_storage_locations(user_id: UserID):
    """Returns the list of available storage locations"""


@app.post(
    f"/{api_vtag}/locations/{{location_id}}:sync",
    response_model=Envelope[TableSynchronisation],
    tags=TAGS_LOCATIONS,
    operation_id="synchronise_meta_data_table",
    summary="Manually triggers the synchronisation of the file meta data table in the database",
)
async def synchronise_meta_data_table(
    location_id: LocationID, dry_run: bool = False, fire_and_forget: bool = False
):
    """Returns an object containing added, changed and removed paths"""


# handlers_files.py


@app.get(
    f"/{api_vtag}/locations/{{location_id}}/files/metadata",
    response_model=Envelope[list[DatasetMetaData]],
    tags=TAGS_FILES,
    operation_id="get_files_metadata",
    summary="Get datasets metadata",
)
async def get_files_metadata(
    location_id: LocationID, uuid_filter: str = "", expand_dirs: bool = True
):
    """list of file meta-datas"""


@app.get(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}/metadata",
    response_model=FileMetaData | Envelope[FileMetaDataGet],
    tags=TAGS_FILES,
    summary="Get File Metadata",
    operation_id="get_file_metadata",
)
async def get_file_metadata(
    location_id: LocationID, file_id: StorageFileID, user_id: UserID
):
    ...


@app.get(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}",
    response_model=Envelope[PresignedLink],
    tags=TAGS_FILES,
    operation_id="download_file",
    summary="Returns download link for requested file",
)
async def download_file(
    location_id: LocationID,
    file_id: StorageFileID,
    user_id: UserID,
    link_type: LinkType = LinkType.PRESIGNED,
):
    """Returns a presigned link"""


@app.put(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}",
    response_model=Envelope[FileUploadSchema] | Envelope[AnyUrl],
    tags=TAGS_FILES,
    operation_id="upload_file",
    summary="Returns upload link",
)
async def upload_file(
    location_id: LocationID,
    file_id: StorageFileID,
    file_size: ByteSize | None,
    link_type: LinkType = LinkType.PRESIGNED,
    is_directory: bool = False,
):
    """Return upload object"""


@app.post(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:abort",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_FILES,
    operation_id="abort_upload_file",
)
async def abort_upload_file(
    location_id: LocationID, file_id: StorageFileID, user_id: UserID
):
    """Asks the server to abort the upload and revert to the last valid version if any"""


@app.post(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:complete",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=Envelope[FileUploadCompleteResponse],
    tags=TAGS_FILES,
    operation_id="complete_upload_file",
)
async def complete_upload_file(
    body_item: Envelope[FileUploadCompletionBody],
    location_id: LocationID,
    file_id: StorageFileID,
    user_id: UserID,
):
    """Asks the server to complete the upload"""


@app.post(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}:complete/futures/{{future_id}}",
    response_model=Envelope[FileUploadCompleteFutureResponse],
    tags=TAGS_FILES,
    summary="Check for upload completion",
    operation_id="is_completed_upload_file",
)
async def is_completed_upload_file(
    location_id: LocationID, file_id: StorageFileID, future_id: str, user_id: UserID
):
    """Returns state of upload completion"""


# handlers_health.py


@app.get(
    f"/{api_vtag}/",
    response_model=Envelope[HealthCheck],
    tags=TAGS_HEALTH,
    summary="health check endpoint",
    operation_id="get_health",
)
async def get_health():
    """Current service health"""


@app.get(
    f"/{api_vtag}/status",
    response_model=Envelope[AppStatusCheck],
    tags=TAGS_HEALTH,
    summary="returns the status of the services inside",
    operation_id="get_status",
)
async def get_status():
    ...


# handlers_locations.py


@app.delete(
    f"/{api_vtag}/locations/{{location_id}}/files/{{file_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_FILES,
    operation_id="delete_file",
    summary="Deletes File",
)
async def delete_file(location_id: LocationID, file_id: StorageFileID, user_id: UserID):
    ...


@app.post(
    f"/{api_vtag}/files/{{file_id}}:soft-copy",
    response_model=FileMetaDataGet,
    tags=TAGS_FILES,
    summary="copy file as soft link",
    operation_id="copy_as_soft_link",
)
async def copy_as_soft_link(
    body_item: SoftCopyBody, file_id: StorageFileID, user_id: UserID
):
    ...


# handlers_simcore_s3.py


@app.post(
    f"/{api_vtag}/simcore-s3:access",
    response_model=Envelope[S3Settings],
    tags=TAGS_SIMCORE_S3,
    summary="gets or creates the a temporary access",
    operation_id="get_or_create_temporary_s3_access",
)
async def get_or_create_temporary_s3_access(user_id: UserID):
    ...


@app.post(
    f"/{api_vtag}/simcore-s3/folders",
    response_model=Envelope[TaskGet],
    tags=TAGS_SIMCORE_S3,
    summary="copies folders from project",
    operation_id="copy_folders_from_project",
)
async def copy_folders_from_project(body_item: FoldersBody, user_id: UserID):
    ...


@app.delete(
    f"/{api_vtag}/simcore-s3/folders/{{folder_id}}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_SIMCORE_S3,
    summary="delete folders from project",
    operation_id="delete_folders_of_project",
)
async def delete_folders_of_project(
    folder_id: str, user_id: UserID, node_id: NodeID | None = None
):
    ...


@app.post(
    f"/{api_vtag}/simcore-s3/files/metadata:search",
    response_model=Envelope[FileMetaDataGet],
    tags=TAGS_SIMCORE_S3,
    summary="search for files starting with",
    operation_id="search_files_starting_with",
)
async def search_files_starting_with(user_id: UserID, startswith: str = ""):
    ...


# long_running_tasks.py


@app.get(
    "/",
    response_model=Envelope[TaskGet],
    tags=TAGS_TASKS,
    summary="list current long running tasks",
    operation_id="list_tasks",
)
async def list_tasks():
    ...


@app.get(
    "/{task_id}",
    response_model=Envelope[TaskStatus],
    tags=TAGS_TASKS,
    summary="gets the status of the task",
    operation_id="get_task_status",
)
async def get_task_status():
    ...


@app.get(
    "/{task_id}/result",
    response_model=Any,
    tags=TAGS_TASKS,
    summary="get result of the task",
    operation_id="get_task_result",
)
async def get_task_result():
    ...


@app.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=TAGS_TASKS,
    summary="cancels and removes the task",
    operation_id="cancel_and_delete_task",
)
async def cancel_and_delete_task():
    ...


if __name__ == "__main__":
    from _common import CURRENT_DIR, create_openapi_specs

    create_openapi_specs(app, CURRENT_DIR.parent / "openapi.yaml")


# TODO: regroup by tags all endpoints
