import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from database import get_db

EMAILS_DIR = os.path.join(os.path.dirname(__file__), "sent_emails")
os.makedirs(EMAILS_DIR, exist_ok=True)

def record_and_dispatch_email(order_id, recipient, subject, body_text, body_html, email_type):
    """
    Registra el email en la ficha del pedido (tabla order_emails e historial),
    guarda una copia física en el buzón local sent_emails/ y envía vía SMTP si está configurado.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_db()
    cursor = conn.cursor()

    # 1. Guardar en tabla order_emails para la ficha
    cursor.execute("""
        INSERT INTO order_emails (order_id, recipient_email, subject, body_text, email_type, sent_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'ENVIADO')
    """, (order_id, recipient, subject, body_text, email_type, now_str))

    # 2. Dejar constancia en el historial de la ficha
    cursor.execute("""
        INSERT INTO order_history (order_id, status, comment, timestamp)
        VALUES (?, (SELECT status FROM orders WHERE id = ?), ?, ?)
    """, (order_id, order_id, f"Email enviado a la familia ({recipient}): '{subject}'", now_str))

    # Actualizar orders con último canal y fecha
    cursor.execute("""
        UPDATE orders SET notification_sent_at = ?, notification_channel = 'email' WHERE id = ?
    """, (now_str, order_id))

    conn.commit()
    conn.close()

    # 3. Guardar copia física del archivo de email en disco
    safe_filename = f"{now_str.replace(':', '-').replace(' ', '_')}_{email_type}_{order_id}.html"
    file_path = os.path.join(EMAILS_DIR, safe_filename)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"<!-- RECIPIENT: {recipient} | SUBJECT: {subject} | DATE: {now_str} -->\n" + body_html)
    except Exception as e:
        print(f"Error archivando copia del email: {e}")

    # 4. Intento de envío SMTP si el colegio tiene configurado servidor
    smtp_host = os.environ.get("SMTP_HOST")
    if smtp_host:
        try:
            smtp_port = int(os.environ.get("SMTP_PORT", 587))
            smtp_user = os.environ.get("SMTP_USER")
            smtp_pass = os.environ.get("SMTP_PASS")
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Colegio San Buenaventura <{smtp_user or 'uniformes@colegiosanbuenaventura.es'}>"
            msg["To"] = recipient
            msg.attach(MIMEText(body_text, "plain", "utf-8"))
            msg.attach(MIMEText(body_html, "html", "utf-8"))

            server = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(msg["From"], [recipient], msg.as_string())
            server.quit()
        except Exception as e:
            print(f"Aviso SMTP: no se pudo enviar por red externa ({e}). El email queda registrado en la ficha.")

    return {
        "status": "ENVIADO",
        "recipient": recipient,
        "subject": subject,
        "sent_at": now_str,
        "archive_file": safe_filename
    }

def send_order_confirmation_email(order, items, base_url="http://localhost:5050/"):
    """
    Envía y registra el email de confirmación automática en cuanto la familia realiza la reserva.
    """
    locator = order["locator"]
    student = order["student_name"]
    course = order["student_course"]
    parent = order["parent_name"]
    total = f"{order['total_amount']:.2f} €"
    invoice_url = f"{base_url.rstrip('/')}/factura/{locator}"
    tracking_url = f"{base_url.rstrip('/')}/?locator={locator}"

    # Construir listado de prendas en texto y HTML
    items_text = ""
    items_html_rows = ""
    for it in items:
        sub = f"{it['subtotal']:.2f} €"
        items_text += f"- {it['product_name']} (Talla: {it['size']}) x{it['quantity']} = {sub}\n"
        items_html_rows += f"""
        <tr style="border-bottom: 1px solid #e2e8f0;">
            <td style="padding: 10px 8px; font-weight: 600; color: #1e293b;">{it['product_name']}</td>
            <td style="padding: 10px 8px; text-align: center; color: #475569;"><span style="background: #f1f5f9; padding: 2px 8px; border-radius: 4px; font-family: monospace;">{it['size']}</span></td>
            <td style="padding: 10px 8px; text-align: center; color: #475569;">{it['quantity']}</td>
            <td style="padding: 10px 8px; text-align: right; font-weight: bold; color: #0f172a;">{sub}</td>
        </tr>
        """

    subject = f"Reserva de Uniformes Recibida [{locator}] - Colegio San Buenaventura"

    body_text = f"""Paz y Bien.

Estimada familia de {student} ({parent}):

Le confirmamos que hemos recibido correctamente su solicitud de reserva de uniformes escolares para el curso {course}.

LOCALIZADOR DE RESERVA: {locator}
FECHA: {order['created_at']}

PRENDAS RESERVADAS:
{items_text}
TOTAL ESTIMADO: {total}

ESTADO ACTUAL: PENDIENTE DE PREPARACIÓN
En cuanto el personal de secretaría prepare su paquete, le enviaremos un nuevo correo indicándole que ya puede pasar a recogerlo.

Puede consultar su pedido y descargar su factura proforma oficial en cualquier momento en el siguiente enlace:
{invoice_url}

Para consultar el estado en la web:
{tracking_url}

Atentamente,
Secretaría y Almacén de Uniformes
Colegio San Buenaventura
"""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #334155;">
            <div style="background: linear-gradient(135deg, #002B66 0%, #005CB9 100%); padding: 26px 20px; text-align: center; border-bottom: 4px solid #F5A623;">
                <h1 style="color: #ffffff; margin: 0; font-size: 21px; font-weight: 800; letter-spacing: 1px;">COLEGIO SAN BUENAVENTURA</h1>
                <p style="color: #FEEBC8; margin: 6px 0 0 0; font-size: 12px; font-weight: bold; letter-spacing: 2px;">RESERVA OFICIAL DE UNIFORMIDAD ESCOLAR</p>
            </div>
            
            <div style="padding: 24px;">
                <p style="font-size: 15px; margin-top: 0;"><strong>Paz y Bien.</strong></p>
                <p style="font-size: 14px; line-height: 1.5; color: #475569;">
                    Estimada familia de <strong>{student}</strong>: hemos recibido correctamente su reserva de uniformes escolares para el curso <strong>{course}</strong>.
                </p>

                <div style="background: #f1f5f9; border-left: 4px solid #1b365d; padding: 14px 16px; border-radius: 6px; margin: 20px 0;">
                    <span style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold; display: block;">Localizador de su Pedido</span>
                    <span style="font-size: 22px; font-weight: 900; color: #1b365d; font-family: monospace;">{locator}</span>
                </div>

                <h3 style="font-size: 14px; text-transform: uppercase; letter-spacing: 0.5px; color: #0f172a; margin-bottom: 10px; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px;">Prendas Solicitadas</h3>
                <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 16px;">
                    <thead>
                        <tr style="background: #f8fafc; color: #64748b; font-size: 11px; text-align: left; text-transform: uppercase;">
                            <th style="padding: 8px;">Prenda</th>
                            <th style="padding: 8px; text-align: center;">Talla</th>
                            <th style="padding: 8px; text-align: center;">Uds.</th>
                            <th style="padding: 8px; text-align: right;">Subtotal</th>
                        </tr>
                    </thead>
                    <tbody>
                        {items_html_rows}
                    </tbody>
                    <tfoot>
                        <tr>
                            <td colspan="3" style="padding: 12px 8px; text-align: right; font-weight: bold; font-size: 14px; color: #0f172a;">TOTAL:</td>
                            <td style="padding: 12px 8px; text-align: right; font-weight: 900; font-size: 16px; color: #1b365d;">{total}</td>
                        </tr>
                    </tfoot>
                </table>

                <div style="text-align: center; margin: 25px 0;">
                    <a href="{invoice_url}" style="background-color: #1b365d; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 13px; display: inline-block;">
                        Ver / Imprimir Factura Oficial (PDF)
                    </a>
                </div>

                <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 12px 16px; font-size: 12px; color: #1e3a8a; line-height: 1.5;">
                    <strong>ℹ️ Próximos pasos:</strong><br>
                    Su pedido se encuentra en estado <em>Pendiente de preparación</em>. Tan pronto como esté empaquetado en secretaría, le enviaremos un correo avisándole para que pase a recogerlo.
                </div>
            </div>

            <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 11px; color: #94a3b8;">
                Colegio San Buenaventura • Calle San Buenaventura, s/n • Madrid<br>
                uniformes@colegiosanbuenaventura.es
            </div>
        </div>
    </body>
    </html>
    """

    return record_and_dispatch_email(order["id"], order["parent_email"], subject, body_text, body_html, "confirmacion_reserva")

def send_order_ready_email(order, items, base_url="http://localhost:5050/"):
    """
    Envía y registra el aviso por correo cuando el pedido está LISTO PARA RECOGER.
    """
    locator = order["locator"]
    student = order["student_name"]
    course = order["student_course"]
    parent = order["parent_name"]
    total = f"{order['total_amount']:.2f} €"
    invoice_url = f"{base_url.rstrip('/')}/factura/{locator}"

    subject = f"¡Tu uniforme está LISTO PARA RECOGER! [{locator}] - Colegio San Buenaventura"

    body_text = f"""Paz y Bien.

Estimada familia de {student} ({parent}):

Le informamos desde el Colegio San Buenaventura de que su reserva de uniformes con localizador {locator} ya se encuentra empaquetada y LISTA PARA RECOGER.

DATOS DE RECOGIDA:
- Alumno/a: {student} ({course})
- Localizador: {locator}
- Punto de recogida: Conserjería / Secretaría del Colegio
- Horario de atención: Lunes a Viernes de 09:00 a 13:30 y de 15:30 a 17:30
- Importe de la reserva: {total}

Por favor, indique su código localizador ({locator}) o presente la factura proforma en secretaría. Puede verla o descargarla aquí:
{invoice_url}

Atentamente,
Secretaría y Conserjería
Colegio San Buenaventura
"""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #334155;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #002B66 0%, #005CB9 100%); padding: 26px 20px; text-align: center; border-bottom: 4px solid #F5A623;">
                <h1 style="color: #ffffff; margin: 0; font-size: 21px; font-weight: 800; letter-spacing: 1px;">COLEGIO SAN BUENAVENTURA</h1>
                <p style="color: #FEEBC8; margin: 6px 0 0 0; font-size: 13px; font-weight: bold; letter-spacing: 1px;">✓ ¡UNIFORME LISTO PARA RECOGER!</p>
            </div>
            
            <div style="padding: 24px;">
                <p style="font-size: 15px; margin-top: 0;"><strong>Paz y Bien.</strong></p>
                <p style="font-size: 14px; line-height: 1.5; color: #475569;">
                    Estimada familia de <strong>{student}</strong>: su uniforme escolar ya ha sido empaquetado y preparado en el almacén del colegio. Ya puede pasar a retirarlo.
                </p>

                <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 16px; margin: 20px 0;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #047857; font-weight: bold;">Localizador de Recogida:</div>
                    <div style="font-size: 24px; font-weight: 900; color: #065f46; font-family: monospace; margin: 4px 0 10px 0;">{locator}</div>
                    
                    <ul style="margin: 0; padding-left: 18px; font-size: 13px; color: #064e3b; line-height: 1.6;">
                        <li><strong>Lugar:</strong> Conserjería / Secretaría del Colegio San Buenaventura</li>
                        <li><strong>Horario:</strong> Lunes a Viernes de 09:00 a 13:30 y de 15:30 a 17:30</li>
                        <li><strong>Importe total:</strong> {total}</li>
                    </ul>
                </div>

                <div style="text-align: center; margin: 25px 0;">
                    <a href="{invoice_url}" style="background-color: #065f46; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; font-size: 13px; display: inline-block;">
                        Ver / Imprimir Factura del Pedido
                    </a>
                </div>

                <p style="font-size: 12px; color: #64748b; line-height: 1.5;">
                    * Recuerde que dispone de 15 días tras la recogida para cualquier cambio de talla, conservando las prendas con su etiqueta original y sin marcar.
                </p>
            </div>

            <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 11px; color: #94a3b8;">
                Colegio San Buenaventura • Calle San Buenaventura, s/n • Madrid<br>
                uniformes@colegiosanbuenaventura.es
            </div>
        </div>
    </body>
    </html>
    """

    return record_and_dispatch_email(order["id"], order["parent_email"], subject, body_text, body_html, "listo_para_recoger")


def send_return_request_received_email(order, return_record, base_url="http://localhost:5050/"):
    """
    Notifica a la familia de que su solicitud de cambio de talla o devolución ha sido registrada.
    """
    ticket = return_record["ticket_code"]
    student = order["student_name"]
    parent = order["parent_name"]
    subject = f"Solicitud de Cambio/Devolución recibida [{ticket}] - Colegio San Buenaventura"
    tracking_url = f"{base_url.rstrip('/')}/?locator={order['locator']}"

    items_list = return_record.get("items", [])
    items_desc = ""
    for it in items_list:
        action_txt = f"Cambiar a talla {it.get('new_size')}" if it.get("action") == "cambiar" else "Devolver prenda"
        items_desc += f"- {it.get('product_name')} (Talla actual: {it.get('current_size')} -> {action_txt})\n"

    body_text = f"""Paz y Bien.

Estimada familia de {student} ({parent}):

Hemos recibido correctamente su solicitud de cambio de talla / devolución para el pedido {order['locator']}.

Referencia de solicitud: {ticket}

PRENDAS INDICADAS:
{items_desc}

MOTIVO / NOTAS: {return_record.get('reason', 'N/D')}

¿CUÁL ES EL SIGUIENTE PASO?
1. Secretaría / Almacén verificará la disponibilidad de las nuevas tallas y preparará las prendas de cambio.
2. Le enviaremos un nuevo correo en cuanto las nuevas tallas estén preparadas en secretaría.
3. Al acudir a realizar el cambio, recuerde traer las prendas anteriores con su etiqueta original intacta, sin lavar y sin marcar con nombre.

Puede consultar el estado de su solicitud en cualquier momento en:
{tracking_url}

Atentamente,
Secretaría y Almacén de Uniformes
Colegio San Buenaventura
"""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #334155;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #002B66 0%, #005CB9 100%); padding: 24px 20px; text-align: center; border-bottom: 4px solid #F5A623;">
                <h1 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 800;">COLEGIO SAN BUENAVENTURA</h1>
                <p style="color: #FEEBC8; margin: 6px 0 0 0; font-size: 13px; font-weight: bold;">🔄 SOLICITUD DE CAMBIO / DEVOLUCIÓN REGISTRADA</p>
            </div>
            
            <div style="padding: 24px;">
                <p style="font-size: 15px; margin-top: 0;"><strong>Paz y Bien.</strong></p>
                <p style="font-size: 14px; line-height: 1.5; color: #475569;">
                    Estimada familia de <strong>{student}</strong>: hemos recibido su solicitud de cambio de talla / devolución asociada al pedido <strong>{order['locator']}</strong>.
                </p>

                <div style="background: #f1f5f9; border-left: 4px solid #005CB9; padding: 14px 16px; margin: 18px 0; border-radius: 6px;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #64748b; font-weight: bold;">Código de Gestión de Cambio:</div>
                    <div style="font-size: 20px; font-weight: 900; color: #002B66; font-family: monospace;">{ticket}</div>
                </div>

                <div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 8px; padding: 14px; margin: 18px 0;">
                    <p style="margin: 0 0 8px 0; font-size: 13px; font-weight: bold; color: #92400e;">⚠️ IMPORTANTE PARA EL CANJE EN SECRETARÍA:</p>
                    <ul style="margin: 0; padding-left: 18px; font-size: 12px; color: #78350f; line-height: 1.5;">
                        <li>Las prendas devueltas deben conservar su <strong>etiqueta de fábrica original intacta</strong>.</li>
                        <li>Las prendas no deben haber sido lavadas, estrenadas ni marcadas con el nombre del alumno.</li>
                        <li>Plazo oficial de prueba y cambios: <strong>15 días</strong> desde la recogida del pedido original.</li>
                    </ul>
                </div>

                <p style="font-size: 13px; color: #475569; line-height: 1.5;">
                    En cuanto nuestro personal prepare las nuevas tallas en el almacén del colegio, recibirá una nueva notificación para pasar a realizar el canje en conserjería/secretaría.
                </p>
            </div>

            <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 11px; color: #94a3b8;">
                Colegio San Buenaventura • Calle El Greco, 16 • Madrid • administracion@sanbuenaventura.org
            </div>
        </div>
    </body>
    </html>
    """

    return record_and_dispatch_email(order["id"], order["parent_email"], subject, body_text, body_html, "cambio_solicitado")


def send_return_ready_email(order, return_record, base_url="http://localhost:5050/"):
    """
    Notifica a la familia de que sus nuevas tallas están LISTAS para ser canjeadas en secretaría.
    """
    ticket = return_record["ticket_code"]
    student = order["student_name"]
    parent = order["parent_name"]
    subject = f"¡Tus NUEVAS TALLAS de cambio están LISTAS! [{ticket}] - Colegio San Buenaventura"

    body_text = f"""Paz y Bien.

Estimada familia de {student} ({parent}):

Le informamos de que las nuevas prendas de su solicitud de cambio ({ticket}) ya se encuentran preparadas en Secretaría / Conserjería.

Ya puede pasar a recogerlas en horario habitual de secretaría (Lunes a Viernes de 09:00 a 13:30 y de 15:30 a 17:30).

RECUERDE LLEVAR:
- El código de cambio: {ticket}
- Las prendas a sustituir o devolver con su etiqueta original y sin marcar.

Atentamente,
Secretaría y Almacén de Uniformes
Colegio San Buenaventura
"""

    body_html = f"""
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"></head>
    <body style="font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; background-color: #f8fafc; margin: 0; padding: 20px; color: #334155;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 12px; overflow: hidden; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #065f46 0%, #059669 100%); padding: 24px 20px; text-align: center; border-bottom: 4px solid #F5A623;">
                <h1 style="color: #ffffff; margin: 0; font-size: 20px; font-weight: 800;">COLEGIO SAN BUENAVENTURA</h1>
                <p style="color: #d1fae5; margin: 6px 0 0 0; font-size: 13px; font-weight: bold;">✓ ¡NUEVAS TALLAS LISTAS PARA CANJEAR!</p>
            </div>
            
            <div style="padding: 24px;">
                <p style="font-size: 15px; margin-top: 0;"><strong>Paz y Bien.</strong></p>
                <p style="font-size: 14px; line-height: 1.5; color: #475569;">
                    Estimada familia de <strong>{student}</strong>: las prendas de sustitución correspondientes a su solicitud <strong>{ticket}</strong> ya han sido preparadas y están disponibles en secretaría.
                </p>

                <div style="background: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 8px; padding: 16px; margin: 18px 0;">
                    <div style="font-size: 11px; text-transform: uppercase; color: #047857; font-weight: bold;">Presente este código en ventanilla:</div>
                    <div style="font-size: 22px; font-weight: 900; color: #065f46; font-family: monospace; margin: 4px 0 8px 0;">{ticket}</div>
                    <div style="font-size: 13px; color: #064e3b;">
                        <strong>Punto de recogida:</strong> Secretaría / Conserjería del Colegio (c/ El Greco, 16)<br>
                        <strong>Horario:</strong> Lunes a Viernes de 09:00 a 13:30 y de 15:30 a 17:30
                    </div>
                </div>

                <p style="font-size: 13px; color: #dc2626; font-weight: bold; line-height: 1.5;">
                    ⚠️ Es imprescindible entregar las prendas anteriores en secretaría con su etiqueta original intacta para poder retirar las nuevas.
                </p>
            </div>

            <div style="background: #f8fafc; border-top: 1px solid #e2e8f0; padding: 16px; text-align: center; font-size: 11px; color: #94a3b8;">
                Colegio San Buenaventura • Calle El Greco, 16 • Madrid • administracion@sanbuenaventura.org
            </div>
        </div>
    </body>
    </html>
    """

    return record_and_dispatch_email(order["id"], order["parent_email"], subject, body_text, body_html, "cambio_preparado")
