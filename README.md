# 🏫 Uniformes Colegio San Buenaventura - Sistema de Reserva y Facturación

Aplicación web integral diseñada para la gestión de reservas de uniformes escolares del **Colegio San Buenaventura**. Permite a las familias solicitar sus prendas de forma sencilla, consultar el estado de preparación de su pedido, obtener su factura oficial o comprobante en PDF y recibir aviso cuando su uniforme esté listo para recoger en el colegio.

---

## 🚀 Cómo ejecutar la aplicación

Desde la terminal en el directorio del proyecto:

```bash
cd /Users/jose/.gemini/antigravity/scratch/colegio-san-buenaventura-uniformes
./run.sh
```

El servidor arrancará en **`http://localhost:5050`**.

---

## 🌟 Funcionalidades Principales

### 1. Portal para las Familias (`http://localhost:5050/`)
* **Catálogo interactivo con filtrado**: Navegación por categorías (Infantil, Primaria, Secundaria / Bachillerato, Educación Física / Deporte, Accesorios).
* **Selector dinámico de tallas y cantidades**: Cada prenda cuenta con sus tallas disponibles.
* **Carrito de reserva en tiempo real**: Subtotales, recuento de artículos y desglose estimado.
* **Formulario de reserva colegial**:
  * Nombre y apellidos del alumno/a.
  * Curso escolar (desde 1º Infantil hasta 2º Bachillerato).
  * Nombre del tutor/a, teléfono móvil (para avisos por WhatsApp/SMS), email y DNI (opcional para factura).
  * Observaciones o notas de la familia.
* **Confirmación instantánea con Localizador Único** (ej: `SB-2026-7841`).
* **Seguimiento en directo**: Cualquier familia puede introducir su localizador en la web para consultar la fase en la que se encuentra su reserva:
  * `Recibido` ➔ `En preparación` ➔ `Listo para recoger` ➔ `Entregado`.

---

### 2. Emisión de Facturas y Comprobantes Oficiales (`/factura/<LOCALIZADOR>`)
* Formato homologado con membrete, escudo y datos fiscales del **Colegio San Buenaventura**.
* Desglose de cada prenda, talla elegida, precio unitario, unidades, base imponible, desglose de IVA (21%) y total.
* Datos del alumno, curso y familia.
* Instrucciones de recogida en conserjería/secretaría y política de cambios.
* Botón **"Imprimir / Guardar en PDF"** con maquetación `@media print` optimizada para A4.

---

### 3. Panel de Administración y Secretaría (`http://localhost:5050/admin`)
* **Métricas en tiempo real**: Número de pedidos totales, pendientes, en preparación, listos para entrega e importe económico acumulado.
* **Gestión de estados del pedido**: Cambio en 1 clic de estado (*Pendiente*, *En preparación*, *Listo para recoger*, *Entregado*).
* **Avisar a la Familia**:
  * Genera el enlace directo para enviar un WhatsApp con un solo clic con texto oficial franciscano preformateado indicando que el pedido ya está listo para recoger.
  * Registro de envíos de email y fecha/hora en el historial del pedido.
* **Gestión de Catálogo y Precios**:
  * Formulario para añadir nuevas prendas o editar precios, tallas, nombres e imágenes.
  * Importador masivo preparado para cargar la hoja de cálculo / Excel que nos proporciones.

---

## 📁 Estructura del Proyecto

```
colegio-san-buenaventura-uniformes/
├── app.py                      # Backend API REST y servidor web Flask (puerto 5050)
├── database.py                 # Esquema SQLite (categorías, prendas, pedidos, líneas, historial)
├── seed_data.py                # Datos iniciales y configuración del colegio
├── run.sh                      # Script de arranque rápido
├── uniformes.db                # Base de datos local SQLite
├── templates/
│   ├── index.html              # Portal público de reservas para las familias
│   ├── admin.html              # Panel de gestión y control para secretaría
│   └── invoice.html            # Factura oficial y albarán de entrega imprimible
└── static/
    ├── images/
    │   ├── logo.svg            # Escudo oficial vectorial del Colegio San Buenaventura
    │   └── uniforms/           # Ilustraciones vectoriales de uniformes (polo, jersey, falda, chándal, babi...)
    └── css/
```
