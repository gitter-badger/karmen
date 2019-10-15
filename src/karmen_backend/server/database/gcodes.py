import psycopg2
import psycopg2.extras
from server.database import get_connection, prepare_list_statement

# This intentionally selects limit+1 results in order to properly determine next start_with for pagination
# Take that into account when processing results
def get_gcodes(order_by=None, limit=None, start_with=None, filter=None):
    columns = [
        "id",
        "path",
        "filename",
        "display",
        "absolute_path",
        "uploaded",
        "size",
        "analysis_result",
    ]
    with get_connection() as connection:
        statement = prepare_list_statement(
            connection,
            "gcodes",
            columns,
            order_by=order_by,
            limit=limit,
            start_with=start_with,
            filter=filter,
        )
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(statement)
        data = cursor.fetchall()
        cursor.close()
        return data


def get_gcode(id):
    try:
        if isinstance(id, str):
            id = int(id, base=10)
    except ValueError:
        return None
    with get_connection() as connection:
        cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
        cursor.execute(
            "SELECT id, path, filename, display, absolute_path, uploaded, size, analysis_result from gcodes where id = %s",
            (id,),
        )
        data = cursor.fetchone()
        cursor.close()
        return data


def add_gcode(**kwargs):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT INTO gcodes (path, filename, display, absolute_path, size, analysis_result) values (%s, %s, %s, %s, %s, %s) RETURNING id",
            (
                kwargs["path"],
                kwargs["filename"],
                kwargs["display"],
                kwargs["absolute_path"],
                kwargs["size"],
                psycopg2.extras.Json(kwargs.get("analysis_result", {})),
            ),
        )
        data = cursor.fetchone()
        cursor.close()
        return data[0]


def delete_gcode(id):
    try:
        if isinstance(id, str):
            id = int(id, base=10)
    except ValueError:
        pass
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute("DELETE FROM gcodes WHERE id = %s", (id,))
        cursor.close()


def set_analysis_result(gcode_id, analysis_result):
    with get_connection() as connection:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE gcodes SET analysis_result = %s where id = %s",
            (psycopg2.extras.Json(analysis_result), gcode_id),
        )
        cursor.close()
