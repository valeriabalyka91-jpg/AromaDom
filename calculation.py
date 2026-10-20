import math
import pyodbc

SERVER = r"PRO_SPRINT_M\SQLEXPRESS"
DATABASE = "Aaa"
DRIVER = "ODBC Driver 17 for SQL Server"

def get_connection():
    connection_string = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        "Trusted_Connection=yes;"
        "TrustServerCertificate=yes;"
    )
    return pyodbc.connect(connection_string, timeout=5)

def calculate_product_quantity(
    product_type_id,
    material_type_id,
    raw_material_quantity,
    parameter1,
    parameter2
):
    """
    Рассчитывает целое количество изделий с учётом потерь сырья.

    Возвращает:
        int  — количество готовых изделий;
        -1   — если параметры некорректны, типы не найдены
               или произошла ошибка расчёта.
    """

    if isinstance(product_type_id, bool) or not isinstance(product_type_id, int):
        return -1

    if isinstance(material_type_id, bool) or not isinstance(material_type_id, int):
        return -1

    if isinstance(raw_material_quantity, bool):
        return -1

    if not isinstance(raw_material_quantity, int):
        return -1

    if product_type_id <= 0 or material_type_id <= 0:
        return -1

    if raw_material_quantity < 0:
        return -1

    try:
        parameter1 = float(parameter1)
        parameter2 = float(parameter2)
    except (TypeError, ValueError, OverflowError):
        return -1

    if not math.isfinite(parameter1) or not math.isfinite(parameter2):
        return -1

    if parameter1 <= 0 or parameter2 <= 0:
        return -1

    connection = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT TypeCoefficient
            FROM dbo.ProductTypes
            WHERE ProductTypeId = ?;
        """, product_type_id)

        product_type = cursor.fetchone()

        if product_type is None:
            return -1

        cursor.execute("""
            SELECT LossPercent
            FROM dbo.MaterialTypes
            WHERE MaterialTypeId = ?;
        """, material_type_id)

        material_type = cursor.fetchone()

        if material_type is None:
            return -1

        coefficient = float(product_type[0])
        loss_percent = float(material_type[0])

        if not math.isfinite(coefficient) or coefficient <= 0:
            return -1

        if not math.isfinite(loss_percent):
            return -1

        if loss_percent < 0 or loss_percent > 100:
            return -1

        material_per_product = (
            parameter1 * parameter2 * coefficient
        )

        if (
            not math.isfinite(material_per_product)
            or material_per_product <= 0
        ):
            return -1

        usable_material = (
            raw_material_quantity * (1 - loss_percent / 100)
        )

        result = math.floor(
            usable_material / material_per_product
        )

        return max(0, result)

    except (pyodbc.Error, TypeError, ValueError, OverflowError):
        return -1

    finally:
        if connection is not None:
            connection.close()