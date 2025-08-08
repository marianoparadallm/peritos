# scraping_backend.py

import time
import sys
import argparse
import os
import glob
import pandas as pd
from datetime import datetime, timedelta

# Selenium y BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup

# Cargar variables de entorno desde un archivo .env si está presente
from dotenv import load_dotenv

load_dotenv()

# Firebase
import firebase_admin
from firebase_admin import credentials, firestore

# Para ejecutar scraping en paralelo
import concurrent.futures

########################################
# Inicializa Firebase (si no está ya inicializado)
########################################
# Es importante que el archivo pjn.json esté en la ruta correcta.
# Considera usar una variable de entorno para la ruta del archivo de credenciales.
try:
    if not firebase_admin._apps:  # Solo inicializar si no hay apps existentes
        cred = credentials.Certificate("pjn.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
except Exception as e:
    print(f"Error fatal: No se pudo inicializar Firebase en scraping_backend.py: {e}")
    print("Asegúrate de que 'pjn.json' es correcto y accesible.")
    db = None  # Para evitar más errores si Firebase no se inicializa
    # Podrías querer que el script termine aquí si Firebase es esencial.
    # sys.exit("Saliendo debido a error de inicialización de Firebase.")

########################################
# Carga de credenciales desde variables de entorno
########################################
def _load_usuarios_contrasenas():
    dnis = os.getenv("DNIS", "")
    usuarios = {}
    for dni in [d.strip() for d in dnis.split(",") if d.strip()]:
        pwd = os.getenv(f"PASS_{dni}")
        nombre = os.getenv(f"NAME_{dni}")
        if pwd and nombre:
            usuarios[dni] = {"contrasena": pwd, "nombre": nombre}
    return usuarios


usuarios_contrasenas = _load_usuarios_contrasenas()


########################################
# Funciones auxiliares
########################################
def parse_fecha(value_str):
    """Parsea una cadena de fecha en formato DD/MM/YYYY a objeto datetime."""
    if not isinstance(value_str, str):
        return None  # O manejar como error
    try:
        return datetime.strptime(value_str, "%d/%m/%Y")
    except ValueError:
        # Podrías intentar otros formatos o devolver None/lanzar error
        print(f"Advertencia: No se pudo parsear la fecha '{value_str}' con formato DD/MM/YYYY.")
        return None


def normalize_causa(causa_str):
    """Normaliza el string de la causa para usarlo en IDs de documento."""
    if not isinstance(causa_str, str):
        return "unknown_causa"
    return causa_str.replace(" ", "").replace("/", "_").replace("-", "_").lower()


########################################
# Configuración de WebDriver (similar a acciones_backend)
########################################
def _get_scraper_webdriver():
    """Configura y devuelve una instancia de WebDriver para scraping."""
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")  # Modo headless es preferible para scraping
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-application-cache")
    chrome_options.add_argument("--log-level=3")  # Menos logs de Chrome
    chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])  # Suprimir logs de DevTools

    # IMPORTANTE: ChromeDriver path
    try:
        service = Service()  # Intenta usar chromedriver del PATH
    except WebDriverException:
        chrome_driver_path = "./chromedriver.exe" if os.name == 'nt' else "./chromedriver"
        if not os.path.exists(chrome_driver_path):
            # Este print será visible si el script se ejecuta directamente
            print(f"Error fatal: ChromeDriver no encontrado en PATH ni en {chrome_driver_path}.")
            # Si el script es llamado por la app NiceGUI, este error podría no ser visible directamente allí.
            # Es crucial que chromedriver esté accesible.
            raise FileNotFoundError(f"ChromeDriver no encontrado. El scraping no puede continuar.")
        service = Service(executable_path=chrome_driver_path)

    return webdriver.Chrome(service=service, options=chrome_options)


########################################
# Scraping para un usuario
########################################
def scrapingPJN(dni_usuario):
    if not db:  # Verificar si Firebase está disponible
        return (f"Error crítico: Cliente Firestore no disponible para DNI {dni_usuario}. Saltando scraping.", [])

    if dni_usuario not in usuarios_contrasenas:
        return (f"Advertencia: No se encontró el DNI {dni_usuario} en la lista de usuarios. Saltando.", [])

    datos_usuario = usuarios_contrasenas[dni_usuario]
    contrasena = datos_usuario["contrasena"]
    perito_nombre = datos_usuario["nombre"]

    print(f"Iniciando scraping para {perito_nombre} (DNI: {dni_usuario})...")
    driver = None  # Inicializar driver a None
    try:
        driver = _get_scraper_webdriver()
        driver.get(
            "https://sso.pjn.gov.ar/auth/realms/pjn/protocol/openid-connect/"
            "auth?client_id=pjn-portal&redirect_uri=https%3A%2F%2Fportalpjn.pjn.gov.ar%2F&"
            "response_mode=fragment&response_type=code&scope=openid"
        )

        # Login con esperas explícitas
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.ID, "username"))).send_keys(dni_usuario)
        driver.find_element(By.ID, "password").send_keys(contrasena)
        driver.find_element(By.ID, "kc-login").click()

        # Esperar a que la página de novedades cargue.
        # El selector 'tr.MuiBox-root' parece ser para las filas de la tabla.
        # Aumentar el timeout si la página tarda mucho en cargar.
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "tr.MuiBox-root"))
        )

        # Reintentos para obtener elementos si la página carga dinámicamente
        max_retries = 3
        elements = []
        for attempt in range(max_retries):
            html_code = driver.page_source
            soup = BeautifulSoup(html_code, "lxml")
            # El selector original era "tr", class_="MuiBox-root".
            # MuiBox-root podría ser un div dentro del tr, o el tr mismo.
            # Si MuiBox-root es un div DENTRO de celdas de la tabla, el selector debe ser más específico.
            # Asumiendo que 'tr.MuiBox-root' es correcto para las filas.
            elements = soup.select("tr.MuiBox-root")  # Usar select para CSS selectors
            if elements:
                break
            print(
                f"Intento {attempt + 1}/{max_retries}: No se encontraron elementos para {perito_nombre}. Reintentando en 5s...")
            time.sleep(5)
            driver.refresh()  # Refrescar la página puede ayudar
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.CSS_SELECTOR, "tr.MuiBox-root")))

        if not elements:
            msg = f"No se encontraron actualizaciones (elementos 'tr.MuiBox-root') para {perito_nombre} después de varios intentos."
            print(msg)
            if driver: driver.quit()
            return (msg, [])

        summary_text = f"Scraping para {perito_nombre}: Se encontraron {len(elements)} elementos."
        print(summary_text)
        data_rows = []

        for element_tr in elements:
            try:
                td_tags = element_tr.find_all("td")  # Buscar 'td' dentro de cada 'tr'
                if len(td_tags) < 3:  # Verificar que haya suficientes celdas
                    print(
                        f"Advertencia: Fila con estructura inesperada para {perito_nombre}, se omite: {element_tr.get_text(strip=True, separator=' | ')}")
                    continue

                tipo_raw = td_tags[0].text.strip()
                # La fecha parece estar en td_tags[2] según el código original
                fecha_str = td_tags[2].text.strip()

                # Selectores más robustos para Causa y Nombre (ajustar si la estructura HTML cambia)
                # Estos selectores son cruciales y deben coincidir exactamente con el HTML.
                causa_elem = element_tr.select_one("p.MuiTypography-root.MuiTypography-body1.w-full.css-11dlpbt")
                nombre_elem = element_tr.select_one("p.MuiTypography-root.MuiTypography-body1.w-full.italic.css-4icvzy")

                if causa_elem is None or nombre_elem is None:
                    print(
                        f"Advertencia: No se encontró 'Causa' o 'Nombre' en una fila para {perito_nombre}. Fila: {element_tr.get_text(strip=True, separator=' | ')}")
                    continue

                causa = causa_elem.text.strip()
                nombre = nombre_elem.text.strip()

                # Extraer link (aria-label='Ver Causa')
                link_elem = element_tr.find("a", attrs={"aria-label": "Ver Causa"})
                link = link_elem.get("href", "") if link_elem else ""

                # Mapeo de Tipo
                tipo_mapeado = "NOVEDAD"
                if tipo_raw.lower() == "d":  # "d" parece ser el valor original para "NOVEDAD"
                    tipo_mapeado = "NOVEDAD"
                elif tipo_raw.lower() == "n":  # "n" para "NOTIFICACION"
                    tipo_mapeado = "NOTIFICACION"
                else:  # Otros tipos, usar el valor raw o un default
                    tipo_mapeado = tipo_raw if tipo_raw else "DESCONOCIDO"

                # Parsear la fecha
                fecha_dt = parse_fecha(fecha_str)  # Usar la función de parseo
                if not fecha_dt:
                    print(
                        f"Advertencia: Fecha inválida '{fecha_str}' para {perito_nombre} en causa '{causa}'. Se usará fecha actual como placeholder o se omitirá.")
                    # Podrías decidir omitir la fila o usar una fecha por defecto.
                    # Por ahora, la fila se incluirá con Fecha=None, que luego se manejará.

                row = {
                    "Perito": perito_nombre,  # Usar el nombre completo del perito
                    "Tipo": tipo_mapeado,
                    "Causa": causa,
                    "Nombre": nombre,
                    "Fecha": fecha_dt,  # Guardar como objeto datetime
                    "Link": link,
                    "ScrapedAt": datetime.now()  # Timestamp de cuándo se scrapeó
                }
                data_rows.append(row)

            except Exception as e_row:
                print(
                    f"Error procesando una fila para {perito_nombre}: {e_row}. Fila: {element_tr.get_text(strip=True, separator=' | ')}")
                continue

        if driver: driver.quit()
        return (summary_text, data_rows)

    except TimeoutException:
        msg = f"Timeout durante el scraping para {perito_nombre}. La página no cargó a tiempo o un elemento esperado no apareció."
        print(msg)
        if driver: driver.quit()
        return (msg, [])
    except WebDriverException as e_wd:
        msg = f"Error de WebDriver durante scraping para {perito_nombre}: {e_wd}"
        print(msg)
        if driver: driver.quit()
        return (msg, [])
    except Exception as e_main:
        msg = f"Error inesperado durante scraping para {perito_nombre}: {e_main}"
        print(msg)
        if driver: driver.quit()  # Asegurarse de cerrar el driver en caso de error
        return (msg, [])


########################################
# Guardar en Firestore
########################################
def saveToFirestore(rows_data):
    if not db:  # Verificar si Firebase está disponible
        print("Error crítico: Cliente Firestore no disponible. No se pueden guardar los datos.")
        return 0

    if not rows_data:
        print("No hay datos para guardar en Firestore.")
        return 0

    batch = db.batch()
    saved_count = 0
    for row in rows_data:
        try:
            # Asegurar que 'Fecha' es un objeto datetime para strftime, o manejar si es None
            fecha_dt = row.get("Fecha")
            if isinstance(fecha_dt, datetime):
                fecha_key_str = fecha_dt.strftime("%d-%m-%Y")
            else:  # Si es None o no es datetime (ej. por error de parseo)
                fecha_key_str = "unknown_date"  # O manejar de otra forma

            norm_causa_str = normalize_causa(row.get("Causa", ""))

            # Construir ID de documento único y consistente
            # Incluir DNI o un ID único del perito si 'Perito' (nombre) no es siempre único o puede cambiar.
            # Por ahora, se usa el nombre del perito como en el original.
            doc_id = f"{row.get('Perito', 'unknown_perito')}_{row.get('Tipo', 'unknown_type')}_{fecha_key_str}_{norm_causa_str}"
            doc_id = doc_id.replace(" ", "_").lower()  # Normalizar el ID final

            doc_ref = db.collection("novedades").document(doc_id)

            # Convertir datetime a timestamp de Firestore para la serialización correcta
            data_to_save = row.copy()
            if isinstance(data_to_save.get("Fecha"), datetime):
                data_to_save["Fecha"] = data_to_save["Fecha"]  # Firestore maneja datetime directamente
            if isinstance(data_to_save.get("ScrapedAt"), datetime):
                data_to_save["ScrapedAt"] = data_to_save["ScrapedAt"]

            # Añadir campos de control/estado por defecto si no existen
            if 'Aceptada' not in data_to_save:
                data_to_save['Aceptada'] = False
            if 'EscritoPresentado' not in data_to_save:
                data_to_save['EscritoPresentado'] = False
            if 'Resumen' not in data_to_save:  # Para evitar que falte si resumir_pdf no se ha ejecutado
                data_to_save['Resumen'] = ""

            batch.set(doc_ref, data_to_save,
                      merge=True)  # Usar merge=True para no sobrescribir campos existentes como 'Aceptada' si ya fueron modificados
            saved_count += 1
            if saved_count % 499 == 0:  # Firestore batch limit es 500
                print(
                    f"Realizando commit de batch de {saved_count % 499 if saved_count % 499 != 0 else 499} documentos...")
                batch.commit()
                batch = db.batch()  # Nuevo batch
        except Exception as e:
            print(f"Error preparando datos para Firestore para la fila: {row}. Error: {e}")
            # Podrías decidir si continuar con las otras filas o detenerte.

    if saved_count % 499 != 0:  # Commit del último batch si no estaba vacío
        print(f"Realizando commit del batch final de {saved_count % 499} documentos...")
        batch.commit()

    print(f"Total de {saved_count} registros procesados para Firestore.")
    return saved_count


########################################
# Scraping en paralelo para todos
########################################
def run_all_scraping_concurrently():
    start_time_total = datetime.now()
    print(f"Inicio de scraping concurrente a las {start_time_total.strftime('%d/%m/%Y %H:%M:%S')}")

    if not db:
        print("Scraping abortado: Cliente Firestore no disponible.")
        return

    all_user_dnis = list(usuarios_contrasenas.keys())
    all_scraped_data = []

    # Ajustar max_workers según los recursos de tu máquina y los límites del sitio web.
    # Un número muy alto puede sobrecargar tu sistema o el servidor web.
    num_workers = min(4, len(all_user_dnis))  # No más de 4 workers o el número de usuarios
    print(f"Usando hasta {num_workers} workers concurrentes.")

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
        future_to_dni = {executor.submit(scrapingPJN, dni): dni for dni in all_user_dnis}
        for future in concurrent.futures.as_completed(future_to_dni):
            dni = future_to_dni[future]
            try:
                summary_msg, user_rows = future.result()
                # summary_msg ya se imprime dentro de scrapingPJN o al retornar
                if user_rows:
                    all_scraped_data.extend(user_rows)
            except Exception as e_future:
                # Este error es si la tarea en sí misma (el future) falló catastróficamente.
                print(f"Error crítico ejecutando scraping para DNI {dni}: {e_future}")

    if not all_scraped_data:
        print("No se obtuvieron datos de ningún usuario después del scraping.")
    else:
        print(f"Scraping completado. Total de {len(all_scraped_data)} filas obtenidas de todos los usuarios.")

        # Convertir a DataFrame para filtrado y ordenamiento (opcional, pero útil)
        df = pd.DataFrame(all_scraped_data)

        if not df.empty:
            # Filtrar por fecha si es necesario (ej. solo últimos 30 días)
            # Asegurarse que 'Fecha' es datetime
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')

            # Ejemplo de filtro: mantener solo novedades de los últimos 60 días
            # cutoff_date = datetime.now() - timedelta(days=60)
            # df = df[df['Fecha'] >= cutoff_date] # Mantener NaT si se desea, o filtrar con .notna()

            # Ordenar por fecha (más recientes primero)
            df = df.sort_values('Fecha', ascending=False, na_position='last')

            final_data_to_save = df.to_dict(orient='records')
            print(f"Guardando {len(final_data_to_save)} filas filtradas/ordenadas en Firestore...")
            saveToFirestore(final_data_to_save)
        else:
            print("El DataFrame resultante del scraping está vacío. No se guardará nada.")

    end_time_total = datetime.now()
    print(f"Scraping y actualización completados a las {end_time_total.strftime('%H:%M:%S')}")
    print(f"Duración total del proceso: {end_time_total - start_time_total}")


########################################
# MAIN
########################################
def main():
    parser = argparse.ArgumentParser(description="Script de Scraping PJN y subida a Firestore")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecuta el scraping una sola vez y finaliza."
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=15,  # Intervalo por defecto de 15 minutos
        help="Intervalo en minutos para ejecuciones periódicas (si --once no está presente). Ejemplo: 60"
    )
    args = parser.parse_args()

    if not db:  # Chequeo final antes de empezar
        print("No se puede ejecutar main(): Cliente Firestore no disponible.")
        return

    if args.once:
        run_all_scraping_concurrently()
    else:
        print(f"Iniciando scraping periódico cada {args.interval} minutos. Presiona Ctrl+C para detener.")
        while True:
            try:
                run_all_scraping_concurrently()
                print(f"Siguiente ejecución programada en {args.interval} minutos...")
                time.sleep(args.interval * 60)
            except KeyboardInterrupt:
                print("\nScraping periódico detenido por el usuario.")
                break
            except Exception as e_loop:
                print(f"Error inesperado en el bucle principal de scraping: {e_loop}")
                print(f"Reintentando en {args.interval} minutos...")
                time.sleep(args.interval * 60)


if __name__ == "__main__":
    # Este bloque se ejecuta solo si el script es el punto de entrada principal.
    # Si es importado, no se ejecuta.
    main()
