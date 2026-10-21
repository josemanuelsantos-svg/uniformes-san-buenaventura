import json
from database import get_db, init_db

def make_tiered_sizes(p_2_10, p_12_18, p_20_plus, sizes=None):
    if sizes is None:
        sizes = ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20", "T.22", "T.24", "T.26", "T.28"]
    tier_map = {}
    for s in sizes:
        num_str = s.replace("T.", "").split()[0].strip()
        if num_str.isdigit():
            n = int(num_str)
            if n <= 10:
                tier_map[s] = float(p_2_10)
            elif 12 <= n <= 18:
                tier_map[s] = float(p_12_18)
            else:
                tier_map[s] = float(p_20_plus)
        else:
            tier_map[s] = float(p_20_plus)
    return sizes, tier_map

def seed():
    init_db()
    conn = get_db()
    cursor = conn.cursor()

    # Datos oficiales exactos del pie de la hoja del Colegio San Buenaventura
    settings = {
        "school_name": "Colegio San Buenaventura",
        "school_entity": "Franciscanos Conventuales",
        "school_cif": "R-2800045-G",
        "school_address": "c/ El Greco, 16",
        "school_city": "Madrid",
        "school_postal_code": "28011",
        "school_phone": "91 526 71 61",
        "school_email": "administracion@sanbuenaventura.org",
        "school_web": "www.sanbuenaventura.org",
        "pickup_location": "Conserjería / Secretaría del Colegio (c/ El Greco, 16)",
        "pickup_schedule": "Lunes a Viernes en horario de secretaría",
        "vat_rate": "21",
        "admin_password": "SanBuenaventura2026",
        "admin_password_master": "SanBuenaventura2026",
        "admin_password_operator": "CambiosCSB2026",
        "admin_password_viewer": "ConsultaCSB2026"
    }

    for k, v in settings.items():
        cursor.execute("INSERT OR REPLACE INTO school_settings (key, value) VALUES (?, ?)", (k, v))

    # Categorías oficiales (3 categorías coherentes)
    categories = [
        ("Uniforme infantil", "uniforme-infantil", "Prendas oficiales para Educación Infantil (Babi, Chándal, Camiseta de manga corta y Calcetines blancos)", 1),
        ("Uniforme de Primaria y Secundaria", "uniforme-primaria-secundaria", "Polos, faldas, pantalones de vestir, jerséis de punto y calcetines colegiales", 2),
        ("Chándal de Primaria y Secundaria", "chandal-primaria-secundaria", "Chándal oficial, sudaderas, pantalones deportivos y camisetas técnicas", 3)
    ]

    for name, slug, desc, sort_order in categories:
        cursor.execute("""
            INSERT INTO categories (name, slug, description, sort_order)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(slug) DO UPDATE SET name = excluded.name, description = excluded.description, sort_order = excluded.sort_order
        """, (name, slug, desc, sort_order))

    # Eliminar categorías obsoletas
    cursor.execute("DELETE FROM categories WHERE slug NOT IN ('uniforme-infantil', 'uniforme-primaria-secundaria', 'chandal-primaria-secundaria')")

    cursor.execute("SELECT id, slug FROM categories")
    cat_map = {row["slug"]: row["id"] for row in cursor.fetchall()}

    full_sizes = ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20", "T.22", "T.24", "T.26", "T.28"]
    inf_sizes = ["T.2", "T.3", "T.4", "T.5", "T.6"]
    primaria_secundaria_sizes = ["T.8", "T.10", "T.12", "T.14", "T.16", "T.18", "T.20", "T.22", "T.24", "T.26", "T.28"]

    products_spec = [
        # ================= 1. UNIFORME INFANTIL (Orden 1 al 10) =================
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Babi Escolar Oficial - CSB",
            "code": "BAB-CSB",
            "desc": "Babi oficial obligatorio para Educación Infantil (1º, 2º y 3º). Confeccionado en tejido vichy reglamentario del colegio, canesú marino, bolsillo en contraste y escudo bordado CSB.",
            "base_price": 22.00,
            "tier_data": (["T.2", "T.3", "T.4", "T.5", "T.6", "T.8"], {s: 22.00 for s in ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8"]}),
            "image": "/static/images/uniforms/babi.svg",
            "gender": "Unisex",
            "order": 1
        },
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Chándal Completo Infantil (Sudadera y Pantalón) - CSB",
            "code": "CHA-INF",
            "desc": "Conjunto oficial de chándal infantil: incluye sudadera azul marino con coderas y pantalón con rodilleras de colores. La camiseta de manga corta se adquiere por separado.",
            "base_price": 46.00,
            "tier_data": (inf_sizes, {s: 46.00 for s in inf_sizes}),
            "image": "/static/images/uniforms/chandal-infantil.svg",
            "gender": "Unisex",
            "order": 2
        },
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Sudadera Chándal INFANTIL (Pieza suelta)",
            "code": "SUD-INF",
            "desc": "Sudadera deportiva infantil de chándal azul con cuello polo marino, botones, coderas amarillas y escudo CSB. Suministro individual.",
            "base_price": 26.00,
            "tier_data": (inf_sizes, {s: 26.00 for s in inf_sizes}),
            "image": "/static/images/uniforms/sudadera-chandal-infantil.svg",
            "gender": "Unisex",
            "order": 3
        },
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Pantalón Chándal INFANTIL (Pieza suelta)",
            "code": "PAN-INF",
            "desc": "Pantalón deportivo infantil azul marino con rodilleras reforzadas (una amarilla y otra celeste) y cintura elástica. Suministro individual.",
            "base_price": 21.00,
            "tier_data": (inf_sizes, {s: 21.00 for s in inf_sizes}),
            "image": "/static/images/uniforms/pantalon-chandal-infantil.svg",
            "gender": "Unisex",
            "order": 4
        },
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Camiseta de Manga Corta - INFANTIL",
            "code": "CAM-MC-INF",
            "desc": "Camiseta técnica oficial de deporte CSB, manga corta y cuello con vivos oficiales en contraste. Mismo modelo y diseño que Primaria, adaptada a tallas infantiles para psicomotricidad y deporte (prenda independiente no incluida en el chándal).",
            "base_price": 17.00,
            "tier_data": (inf_sizes, {s: 17.00 for s in inf_sizes}),
            "image": "/static/images/uniforms/camiseta-deporte.svg",
            "gender": "Unisex",
            "order": 5
        },
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Pantalón Corto de Deporte Infantil - CSB",
            "code": "BER-INF",
            "desc": "Bermuda deportiva azul royal oficial con cintura elástica para actividades físicas y psicomotricidad en Educación Infantil.",
            "base_price": 17.00,
            "tier_data": (inf_sizes, {s: 17.00 for s in inf_sizes}),
            "image": "/static/images/uniforms/pantalon-corto-deporte.svg",
            "gender": "Unisex",
            "order": 6
        },
        {
            "category_id": cat_map["uniforme-infantil"],
            "name": "Calcetín Blanco - INFANTIL",
            "code": "CAL-BL-INF",
            "desc": "Calcetín blanco oficial de algodón colegial reforzado para alumnos de Educación Infantil.",
            "base_price": 3.00,
            "tier_data": (inf_sizes, {s: 3.00 for s in inf_sizes}),
            "image": "/static/images/uniforms/calcetin-blanco.svg",
            "gender": "Unisex",
            "order": 7
        },

        # ================= 2. UNIFORME DE PRIMARIA Y SECUNDARIA (Orden 11 al 25) =================
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Polo M/corta - CSB",
            "code": "POL-MC-CSB",
            "desc": "Polo oficial azul celeste de manga corta con ribetes a contraste en cuello y mangas y escudo bordado CSB. Prenda reglamentaria de diario para Primaria y Secundaria.",
            "base_price": 22.00,
            "tier_data": make_tiered_sizes(22.00, 23.00, 25.00, full_sizes),
            "image": "/static/images/uniforms/polo-mcorta.svg",
            "gender": "Unisex",
            "order": 11
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Polo M/larga - CSB (Restos / Tallas sueltas)",
            "code": "POL-ML-CSB",
            "desc": "Polo oficial azul celeste de manga larga con cuello y puños elásticos con ribete y escudo bordado CSB. Prenda a extinguir disponible únicamente en restos de tallas sueltas hasta agotar existencias.",
            "base_price": 23.00,
            "tier_data": make_tiered_sizes(23.00, 24.00, 26.00, full_sizes),
            "image": "/static/images/uniforms/polo-mlarga.svg",
            "gender": "Unisex",
            "order": 12
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Falda uniforme - CSB",
            "code": "FAL-CSB",
            "desc": "Falda oficial con tablas, tejido gris marengo con finos cuadros de líneas azules y tirantes en tallas infantiles.",
            "base_price": 43.00,
            "tier_data": make_tiered_sizes(43.00, 53.00, 56.00, full_sizes),
            "image": "/static/images/uniforms/falda.svg",
            "gender": "Niña",
            "order": 13
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Pantalón vestir largo - CSB",
            "code": "PAN-LG-CSB",
            "desc": "Pantalón largo gris marengo modelo chino oficial con cintura elástica ajustable y corte formal.",
            "base_price": 38.00,
            "tier_data": make_tiered_sizes(38.00, 40.00, 46.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-vestir-largo.svg",
            "gender": "Niño / Unisex",
            "order": 14
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Pantalón vestir corto - CSB",
            "code": "PAN-CT-CSB",
            "desc": "Bermuda gris marengo oficial para meses cálidos con trabillas para cinturón y bolsillos laterales.",
            "base_price": 33.00,
            "tier_data": make_tiered_sizes(33.00, 36.00, 40.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-vestir-corto.svg",
            "gender": "Niño / Unisex",
            "order": 15
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Jersey uniforme - CSB",
            "code": "JER-CSB",
            "desc": "Jersey oficial de punto fino azul colegial con cuello en pico, remates en canalé y escudo bordado CSB.",
            "base_price": 34.00,
            "tier_data": make_tiered_sizes(34.00, 37.00, 40.00, full_sizes),
            "image": "/static/images/uniforms/jersey.svg",
            "gender": "Unisex",
            "order": 16
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Calcetín corto azul marino - CSB",
            "code": "CAL-CT-CSB",
            "desc": "Calcetín corto colegial azul marino de canalé fino en algodón elástico reforzado.",
            "base_price": 2.60,
            "tier_data": (full_sizes, {s: 2.60 for s in full_sizes}),
            "image": "/static/images/uniforms/calcetin-corto.svg",
            "gender": "Unisex",
            "order": 17
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Calcetín largo azul marino - CSB",
            "code": "CAL-LG-CSB",
            "desc": "Calcetín alto colegial azul marino hasta la rodilla, elástico cómodo que no oprime.",
            "base_price": 3.10,
            "tier_data": (full_sizes, {s: 3.10 for s in full_sizes}),
            "image": "/static/images/uniforms/calcetin-largo.svg",
            "gender": "Unisex",
            "order": 18
        },
        {
            "category_id": cat_map["uniforme-primaria-secundaria"],
            "name": "Leotardo azul marino - CSB",
            "code": "LEO-CSB",
            "desc": "Leotardo de algodón elástico azul marino oficial, tacto suave, cálido y resistente.",
            "base_price": 7.70,
            "tier_data": make_tiered_sizes(7.70, 8.70, 9.70, ["T.2", "T.3", "T.4", "T.5", "T.6", "T.8", "T.10", "T.12", "T.14", "T.16"]),
            "image": "/static/images/uniforms/leotardo.svg",
            "gender": "Unisex / Niña",
            "order": 19
        },

        # ================= 3. CHÁNDAL DE PRIMARIA Y SECUNDARIA (Orden 26 al 35) =================
        {
            "category_id": cat_map["chandal-primaria-secundaria"],
            "name": "Chándal Completo - CSB (Sudadera y Pantalón)",
            "code": "CHA-CSB",
            "desc": "Conjunto deportivo oficial completo (sudadera + pantalón). Aviso: La uniformidad actual se suministra por separado (sudadera y pantalón). Este conjunto completo solo se ofrece en restos de tallas sueltas hasta agotar existencias.",
            "base_price": 54.00,
            "tier_data": make_tiered_sizes(54.00, 56.00, 63.00, full_sizes),
            "image": "/static/images/uniforms/chandal-completo.svg",
            "gender": "Unisex",
            "order": 26
        },
        {
            "category_id": cat_map["chandal-primaria-secundaria"],
            "name": "Sudadera de chándal (Pieza suelta) - CSB",
            "code": "SUD-CSB",
            "desc": "Chaqueta deportiva de chándal con cremallera, diseño bicolor azul marino y royal con franja blanca y escudo CSB. Suministro individual de prenda deportiva.",
            "base_price": 31.00,
            "tier_data": make_tiered_sizes(31.00, 31.00, 35.00, full_sizes),
            "image": "/static/images/uniforms/sudadera-chandal.svg",
            "gender": "Unisex",
            "order": 27
        },
        {
            "category_id": cat_map["chandal-primaria-secundaria"],
            "name": "Pantalón de chándal (Pieza suelta) - CSB",
            "code": "PAN-DEP-CSB",
            "desc": "Pantalón de chándal oficial azul marino con paneles laterales royal/blanco, cintura elástica y puños. Suministro individual de prenda deportiva.",
            "base_price": 23.00,
            "tier_data": make_tiered_sizes(23.00, 28.00, 30.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-chandal.svg",
            "gender": "Unisex",
            "order": 28
        },
        {
            "category_id": cat_map["chandal-primaria-secundaria"],
            "name": "Camiseta de deporte - CSB (Primaria y Secundaria)",
            "code": "CAM-DEP-CSB",
            "desc": "Camiseta técnica oficial de deporte blanca con manga royal, franjas diagonales y escudo CSB para Primaria y Secundaria.",
            "base_price": 17.00,
            "tier_data": make_tiered_sizes(17.00, 18.00, 19.00, primaria_secundaria_sizes),
            "image": "/static/images/uniforms/camiseta-deporte.svg",
            "gender": "Unisex",
            "order": 29
        },
        {
            "category_id": cat_map["chandal-primaria-secundaria"],
            "name": "Pantalón corto de deporte - CSB",
            "code": "BER-DEP-CSB",
            "desc": "Bermuda deportiva oficial azul royal con doble franja blanca en pernera izquierda y escudo CSB.",
            "base_price": 17.00,
            "tier_data": make_tiered_sizes(17.00, 18.00, 19.00, full_sizes),
            "image": "/static/images/uniforms/pantalon-corto-deporte.svg",
            "gender": "Unisex",
            "order": 30
        }
    ]

    for p in products_spec:
        sizes, size_prices = p["tier_data"]
        sizes_json = json.dumps(sizes)
        size_prices_json = json.dumps(size_prices)
        cursor.execute("""
            INSERT INTO products (category_id, name, code, description, price, sizes_json, size_prices_json, image_url, gender, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(code) DO UPDATE SET
                category_id = excluded.category_id,
                name = excluded.name,
                description = excluded.description,
                price = excluded.price,
                sizes_json = excluded.sizes_json,
                size_prices_json = excluded.size_prices_json,
                image_url = excluded.image_url,
                gender = excluded.gender,
                sort_order = excluded.sort_order
        """, (
            p["category_id"],
            p["name"],
            p["code"],
            p["desc"],
            p["base_price"],
            sizes_json,
            size_prices_json,
            p["image"],
            p.get("gender", "Unisex"),
            p["order"]
        ))

    conn.commit()
    conn.close()
    print("Catálogo oficial del Colegio San Buenaventura cargado exitosamente.")

if __name__ == "__main__":
    seed()
