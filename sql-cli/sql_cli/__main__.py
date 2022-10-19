import logging
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import print as rprint

import sql_cli
from sql_cli.connections import convert_to_connection, validate_connections
from sql_cli.constants import DEFAULT_AIRFLOW_HOME, DEFAULT_DAGS_FOLDER
from sql_cli.dag_generator import generate_dag
from sql_cli.project import Project
from sql_cli.run_dag import run_dag
from sql_cli.utils.airflow import (
    get_dag,
    retrieve_airflow_database_conn_from_config,
    set_airflow_database_conn,
)

load_dotenv()
app = typer.Typer(add_completion=False)


def set_logger_level(log_level: int) -> None:
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).setLevel(log_level)


set_logger_level(logging.ERROR)


@app.command(help="Print the SQL CLI version.")
def version() -> None:
    rprint("Astro SQL CLI", sql_cli.__version__)


@app.command(help="Print additional information about the project.")
def about() -> None:
    rprint("Find out more: https://github.com/astronomer/astro-sdk/sql-cli")


@app.command(help="Generate the Airflow DAG from a directory of SQL files.")
def generate(
    workflow_name: str = typer.Argument(
        default=...,
        show_default=False,
        help="name of the workflow directory within workflows directory.",
    ),
    env: str = typer.Option(
        default="default",
        help="environment to run in",
    ),
    project_dir: Path = typer.Option(
        None, dir_okay=True, metavar="PATH", help="(Optional) Default: current directory.", show_default=False
    ),
) -> None:
    project_dir_absolute = project_dir.resolve() if project_dir else Path.cwd()
    project = Project(project_dir_absolute)
    project.load_config(env)

    dag_file = generate_dag(
        directory=project.directory / project.workflows_directory / workflow_name,
        dags_directory=project.airflow_dags_folder,
    )
    rprint("The DAG file", dag_file.resolve(), "has been successfully generated. 🎉")


@app.command(
    help="""
    Validate Airflow connection(s) provided in the configuration file for the given environment.
    """
)
def validate(
    project_dir: Path = typer.Argument(
        None, dir_okay=True, metavar="PATH", help="(Optional) Default: current directory.", show_default=False
    ),
    env: str = typer.Option(
        default="default",
        help="(Optional) Environment used to declare the connections to be validated",
    ),
    connection: str = typer.Option(
        default=None,
        help="(Optional) Identifier of the connection to be validated. By default checks all the env connections.",
    ),
) -> None:
    project_dir_absolute = project_dir.resolve() if project_dir else Path.cwd()
    project = Project(project_dir_absolute)

    validate_connections(project=project, environment=env, connection_id=connection)


@app.command(
    help="""
    Run a workflow locally. This task assumes that there is a local airflow DB (can be a SQLite file), that has been
    initialized with Airflow tables.
    """
)
def run(
    workflow_name: str = typer.Argument(
        default=...,
        show_default=False,
        help="name of the workflow directory within workflows directory.",
    ),
    env: str = typer.Option(
        metavar="environment",
        default="default",
        help="environment to run in",
    ),
    project_dir: Path = typer.Option(
        None, dir_okay=True, metavar="PATH", help="(Optional) Default: current directory.", show_default=False
    ),
    verbose: bool = typer.Option(False, help="Whether to show airflow logs", show_default=True),
) -> None:
    project_dir_absolute = project_dir.resolve() if project_dir else Path.cwd()
    project = Project(project_dir_absolute)
    project.update_config(environment=env)
    project.load_config(env)

    connections = {c["conn_id"]: convert_to_connection(c) for c in project.connections}

    # Since we are using the Airflow ORM to interact with connections, we need to tell Airflow to use our airflow.db
    # The usual route is to set $AIRFLOW_HOME before Airflow is imported. However, in the context of the SQL CLI, we
    # decide this during runtime, depending on the project path and SQL CLI configuration.
    airflow_meta_conn = retrieve_airflow_database_conn_from_config(project.directory / project.airflow_home)
    set_airflow_database_conn(airflow_meta_conn)

    dag_file = generate_dag(
        directory=project.directory / project.workflows_directory / workflow_name,
        dags_directory=project.airflow_dags_folder,
    )
    dag = get_dag(dag_id=workflow_name, subdir=dag_file.parent.as_posix(), include_examples=False)
    run_dag(dag, run_conf=project.airflow_config, connections=connections, verbose=verbose)


@app.command(
    help="""
    Initialise a project structure to write workflows using SQL files.

    \b\n
    Examples of usage:
    \b\n
    $ flow init
    \b\n
    $ flow init .
    \b\n
    $ flow init project_name


    \b\n
    By default, the project structure includes:

    ├── config: withholds configuration, e.g. database connections, within each environment directory
    \b\n
    ├── data: directory which contains datasets, including SQLite databases used by the examples
    \b\n
    └── workflows: directory where SQL workflows are declared, by default has two examples of workflow

    \b\n
    Next steps:
    \b\n
    * Update the file `config/default/configuration.yaml` to declare database connections.
    \b\n
    * Create SQL workflows within the `workflows` folder.
    """
)
def init(
    project_dir: Path = typer.Argument(
        None, dir_okay=True, metavar="PATH", help="(Optional) Default: current directory.", show_default=False
    ),
    airflow_home: Path = typer.Option(
        None,
        dir_okay=True,
        help=f"(Optional) Set the Airflow Home. Default: {DEFAULT_AIRFLOW_HOME}",
        show_default=False,
    ),
    airflow_dags_folder: Path = typer.Option(
        None,
        dir_okay=True,
        help=f"(Optional) Set the DAGs Folder. Default: {DEFAULT_DAGS_FOLDER}",
        show_default=False,
    ),
) -> None:
    project_dir_absolute = project_dir.resolve() if project_dir else Path.cwd()
    project = Project(project_dir_absolute, airflow_home, airflow_dags_folder)
    project.initialise()
    rprint("Initialized an Astro SQL project at", project.directory)


if __name__ == "__main__":  # pragma: no cover
    app()