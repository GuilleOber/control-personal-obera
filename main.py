import gspread
from oauth2client.service_account import ServiceAccountCredentials

def conectar_cliente():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        st.secrets["gcp_service_account"],
        scope
    )

    return gspread.authorize(creds)


def guardar_en_sheets(nombre, tipo):
    try:
        client = conectar_cliente()

        now = ahora()
        anio = now.strftime("%Y")
        mes = now.strftime("%m")
        dia = now.strftime("%Y-%m-%d")

        nombre_archivo = f"Asistencia_{anio}_{mes}"

        # ---------------- BUSCAR O CREAR ARCHIVO MENSUAL ----------------
        try:
            spreadsheet = client.open(nombre_archivo)
        except:
            spreadsheet = client.create(nombre_archivo)

            # OPCIONAL: compartir con tu mail personal
            spreadsheet.share("", perm_type="user", role="writer")

        # ---------------- BUSCAR O CREAR HOJA DEL DÍA ----------------
        try:
            worksheet = spreadsheet.worksheet(dia)
        except:
            worksheet = spreadsheet.add_worksheet(title=dia, rows="1000", cols="10")
            worksheet.append_row(["Nombre", "Fecha", "Hora", "Tipo"])

        # ---------------- GUARDAR REGISTRO ----------------
        fecha = now.strftime("%d-%m-%Y")
        hora = now.strftime("%H:%M:%S")

        worksheet.append_row([nombre, fecha, hora, tipo])

    except Exception as e:
        st.error(f"Error Sheets: {e}")
