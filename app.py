from calculation import calculate_product_quantity

from decimal import Decimal, InvalidOperation

from flask import Flask, render_template, request, redirect, url_for, flash

import pyodbc

app = Flask(__name__)

app.secret_key = "aromadom-materials-session-key"

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

def get_materials():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""

            SELECT

                m.MaterialId,

                m.MaterialName,

                m.MaterialTypeId,

                mt.TypeName AS MaterialType,

                m.UnitId,

                u.Symbol AS UnitSymbol,

                u.UnitName,

                m.UnitPrice,

                m.StockQuantity,

                m.MinimumQuantity,

                m.PackageQuantity,

                COALESCE(

                    (

                        SELECT SUM(pm.QuantityPerUnit)

                        FROM dbo.ProductMaterials AS pm

                        WHERE pm.MaterialId = m.MaterialId

                    ),

                    0

                ) AS RequiredQuantity

            FROM dbo.Materials AS m

            INNER JOIN dbo.MaterialTypes AS mt

                ON mt.MaterialTypeId = m.MaterialTypeId

            INNER JOIN dbo.Units AS u

                ON u.UnitId = m.UnitId

            WHERE m.IsActive = 1

            ORDER BY mt.TypeName, m.MaterialName;

        """)

        columns = [column[0] for column in cursor.description]

        return [

            dict(zip(columns, row))

            for row in cursor.fetchall()

        ]

    finally:

        connection.close()

def get_material(material_id):

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""

            SELECT

                MaterialId,

                MaterialName,

                MaterialTypeId,

                UnitId,

                UnitPrice,

                StockQuantity,

                MinimumQuantity,

                PackageQuantity

            FROM dbo.Materials

            WHERE MaterialId = ? AND IsActive = 1;

        """, material_id)

        row = cursor.fetchone()

        if row is None:

            return None

        columns = [column[0] for column in cursor.description]

        return dict(zip(columns, row))

    finally:

        connection.close()

def get_form_options():

    connection = get_connection()

    try:

        cursor = connection.cursor()

        cursor.execute("""

            SELECT MaterialTypeId, TypeName

            FROM dbo.MaterialTypes

            ORDER BY TypeName;

        """)

        material_types = [

            {"id": row.MaterialTypeId, "name": row.TypeName}

            for row in cursor.fetchall()

        ]

        cursor.execute("""

            SELECT UnitId, Symbol, UnitName

            FROM dbo.Units

            ORDER BY Symbol;

        """)

        units = [

            {

                "id": row.UnitId,

                "symbol": row.Symbol,

                "name": row.UnitName

            }

            for row in cursor.fetchall()

        ]

        return material_types, units

    finally:

        connection.close()

def render_material_form(is_edit=False, material=None, form_data=None):

    material_types, units = get_form_options()

    return render_template(

        "material_form.html",

        is_edit=is_edit,

        material=material,

        form_data=form_data or {},

        material_types=material_types,

        units=units

    )

def parse_decimal(field_name, label, minimum, max_digits=3):

    raw_value = request.form.get(field_name, "").strip()

    if not raw_value:

        raise ValueError(f"Заполните поле «{label}».")

    try:

        value = Decimal(raw_value.replace(",", "."))

    except InvalidOperation:

        raise ValueError(

            f"Поле «{label}» должно содержать корректное число."

        )

    if not value.is_finite():

        raise ValueError(f"Поле «{label}» содержит недопустимое число.")

    if value < minimum:

        raise ValueError(

            f"Поле «{label}» не может быть меньше {minimum}."

        )

    decimal_places = max(-value.as_tuple().exponent, 0)

    if decimal_places > max_digits:

        raise ValueError(

            f"Поле «{label}» допускает не более {max_digits} знаков "

            "после запятой."

        )

    return value

def save_material(material_id=None):

    form_data = request.form.to_dict()

    try:

        material_name = request.form.get("material_name", "").strip()

        if not material_name:

            raise ValueError("Введите наименование материала.")

        if len(material_name) > 250:

            raise ValueError(

                "Наименование материала не должно превышать 250 символов."

            )

        try:

            material_type_id = int(request.form.get("material_type_id", ""))

            unit_id = int(request.form.get("unit_id", ""))

        except (ValueError, TypeError):

            raise ValueError(

                "Выберите тип материала и единицу измерения из списка."

            )

        unit_price = parse_decimal(

            "unit_price", "Цена за единицу", Decimal("0"), 2

        )

        package_quantity = parse_decimal(

            "package_quantity", "Количество в упаковке",

            Decimal("0.001"), 3

        )

        stock_quantity = parse_decimal(

            "stock_quantity", "Количество на складе",

            Decimal("0"), 3

        )

        minimum_quantity = parse_decimal(

            "minimum_quantity", "Минимальное количество",

            Decimal("0"), 3

        )

        connection = get_connection()

        try:

            cursor = connection.cursor()

            cursor.execute(

                "SELECT 1 FROM dbo.MaterialTypes WHERE MaterialTypeId = ?;",

                material_type_id

            )

            if cursor.fetchone() is None:

                raise ValueError("Выбранный тип материала не существует.")

            cursor.execute(

                "SELECT 1 FROM dbo.Units WHERE UnitId = ?;",

                unit_id

            )

            if cursor.fetchone() is None:

                raise ValueError("Выбранная единица измерения не существует.")

            cursor.execute("""

                SELECT MaterialId

                FROM dbo.Materials

                WHERE MaterialName = ?

                  AND (? IS NULL OR MaterialId <> ?);

            """, material_name, material_id, material_id)

            if cursor.fetchone() is not None:

                raise ValueError(

                    "Материал с таким наименованием уже существует. "

                    "Введите другое наименование."

                )

            if material_id is None:

                cursor.execute("""

                    INSERT INTO dbo.Materials (

                        MaterialName,

                        MaterialTypeId,

                        UnitId,

                        UnitPrice,

                        StockQuantity,

                        MinimumQuantity,

                        PackageQuantity,

                        IsActive

                    )

                    VALUES (?, ?, ?, ?, ?, ?, ?, 1);

                """,

                    material_name,

                    material_type_id,

                    unit_id,

                    unit_price,

                    stock_quantity,

                    minimum_quantity,

                    package_quantity

                )

                success_message = "Материал успешно добавлен."

            else:

                cursor.execute("""

                    UPDATE dbo.Materials

                    SET MaterialName = ?,

                        MaterialTypeId = ?,

                        UnitId = ?,

                        UnitPrice = ?,

                        StockQuantity = ?,

                        MinimumQuantity = ?,

                        PackageQuantity = ?

                    WHERE MaterialId = ? AND IsActive = 1;

                """,

                    material_name,

                    material_type_id,

                    unit_id,

                    unit_price,

                    stock_quantity,

                    minimum_quantity,

                    package_quantity,

                    material_id

                )

                if cursor.rowcount == 0:

                    raise ValueError(

                        "Материал не найден или был деактивирован. "

                        "Вернитесь к списку и выберите материал заново."

                    )

                success_message = "Изменения материала успешно сохранены."

            connection.commit()

        except Exception:

            connection.rollback()

            raise

        finally:

            connection.close()

        flash(success_message, "success")

        return redirect(url_for("index"))

    except ValueError as error:

        flash(str(error), "error")

    except pyodbc.IntegrityError:

        flash(

            "Не удалось сохранить материал: данные нарушают ограничение "

            "базы данных. Проверьте уникальность наименования и значения.",

            "error"

        )

    except pyodbc.Error:

        app.logger.exception("Ошибка SQL Server при сохранении материала")

        flash(

            "Не удалось сохранить материал из-за ошибки базы данных. "

            "Проверьте подключение к SQL Server и структуру таблиц.",

            "error"

        )

    except Exception:

        app.logger.exception("Непредвиденная ошибка сохранения")

        flash(

            "Произошла непредвиденная ошибка. Повторите попытку. "

            "Если ошибка повторяется, проверьте журнал приложения.",

            "error"

        )

    if material_id is None:

        return render_material_form(

            is_edit=False,

            form_data=form_data

        )

    material = get_material(material_id)

    if material is None:

        flash("Материал больше недоступен для редактирования.", "error")

        return redirect(url_for("index"))

    return render_material_form(

        is_edit=True,

        material=material,

        form_data=form_data

    )

@app.route("/")

def index():

    try:

        materials = get_materials()

        shortage_count = sum(

            1 for item in materials

            if item["StockQuantity"] < item["MinimumQuantity"]

        )

        return render_template(

            "index.html",

            materials=materials,

            shortage_count=shortage_count,

            error=None

        )

    except Exception:

        app.logger.exception("Ошибка загрузки материалов")

        return render_template(

            "index.html",

            materials=[],

            shortage_count=0,

            error=(

                "Не удалось получить материалы из базы данных. "

                "Проверьте SQL Server, имя базы AromaDom и наличие таблиц."

            )

        ), 500

@app.route("/materials/add", methods=["GET", "POST"])

def add_material():

    if request.method == "POST":

        return save_material()

    try:

        return render_material_form()

    except Exception:

        app.logger.exception("Ошибка открытия формы добавления")

        flash(

            "Не удалось загрузить списки типов материалов и единиц. "

            "Проверьте подключение к базе данных.",

            "error"

        )

        return redirect(url_for("index"))

@app.route("/materials/<int:material_id>/edit", methods=["GET", "POST"])

def edit_material(material_id):

    try:

        material = get_material(material_id)

        if material is None:

            flash(

                "Материал не найден или больше не активен. "

                "Выберите материал из актуального списка.",

                "error"

            )

            return redirect(url_for("index"))

        if request.method == "POST":

            return save_material(material_id)

        return render_material_form(

            is_edit=True,

            material=material

        )

    except Exception:

        app.logger.exception("Ошибка открытия формы редактирования")

        flash(

            "Не удалось открыть материал. Проверьте подключение к базе данных.",

            "error"

        )

        return redirect(url_for("index"))

@app.route("/materials/<int:material_id>/products")
def products_by_material(material_id):
    connection = None

    try:
        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                m.MaterialId,
                m.MaterialName,
                u.Symbol AS UnitSymbol
            FROM dbo.Materials AS m
            INNER JOIN dbo.Units AS u
                ON u.UnitId = m.UnitId
            WHERE m.MaterialId = ? AND m.IsActive = 1;
        """, material_id)

        row = cursor.fetchone()

        if row is None:
            flash("Материал не найден или неактивен.", "error")
            return redirect(url_for("index"))

        material = {
            "MaterialId": row.MaterialId,
            "MaterialName": row.MaterialName,
            "UnitSymbol": row.UnitSymbol
        }

        cursor.execute("""
            SELECT
                p.ProductId,
                p.Article,
                p.ProductName,
                pt.TypeName AS ProductType,
                pm.QuantityPerUnit AS RequiredQuantity
            FROM dbo.ProductMaterials AS pm
            INNER JOIN dbo.Products AS p
                ON p.ProductId = pm.ProductId
            INNER JOIN dbo.ProductTypes AS pt
                ON pt.ProductTypeId = p.ProductTypeId
            WHERE pm.MaterialId = ?
              AND p.IsActive = 1
            ORDER BY p.ProductName;
        """, material_id)

        products = []
        for item in cursor.fetchall():
            products.append({
                "ProductId": item.ProductId,
                "Article": item.Article,
                "ProductName": item.ProductName,
                "ProductType": item.ProductType,
                "RequiredQuantity": item.RequiredQuantity
            })

        return render_template(
            "products_by_material.html",
            material=material,
            products=products
        )

    except Exception:
        app.logger.exception(
            "Ошибка загрузки продукции для материала %s",
            material_id
        )
        flash("Не удалось загрузить список продукции.", "error")
        return redirect(url_for("index"))

    finally:
        if connection is not None:
            connection.close()

if __name__ == "__main__":

    print("Запуск системы учёта материалов «Арома Дом»...")

    app.run(host="127.0.0.1", port=5000, debug=False)