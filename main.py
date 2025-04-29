import streamlit as st
import requests
import pandas as pd
import re
from decouple import config
from datetime import datetime
import pytz

utc = pytz.UTC
santiago = pytz.timezone('America/Santiago')


CANVAS_URL = config("URL")
API_TOKEN = config("TOKEN")
HEADERS = {"Authorization": f"Bearer {API_TOKEN}"}

subaccount_diplomado = 39
subaccount_magister = 42

session = requests.Session()
session.headers.update(HEADERS)

def parse_input(text):
    ids = re.split(r"[,\s]+", text)
    return [id_.strip() for id_ in ids if id_.strip()]
  
def canvas_request(session, method, endpoint, payload=None, paginated=False):
    if not CANVAS_URL:
        raise ValueError("BASE_URL no está configurada. Usa set_base_url() para establecerla.")

    url = f"{CANVAS_URL}{endpoint}"
    results = []
    
    try:
        while url:
            if method.lower() == "get":
                response = session.get(url, json=payload)
            elif method.lower() == "post":
                response = session.post(url, json=payload)
            elif method.lower() == "put":
                response = session.put(url, json=payload)
            elif method.lower() == "delete":
                response = session.delete(url)
            else:
                print("Método HTTP no soportado")
                return None

            if not response.ok:
                print(f"Error en la petición a {url} ({response.status_code}): {response.text}")
                return None

            data = response.json()
            if paginated:
                results.extend(data) 
                
                url = response.links.get("next", {}).get("url")
            else:
                return data

        return results if paginated else None

    except requests.exceptions.RequestException as e:
        print(f"Excepción en la petición a {url}: {e}")
        return None


st.set_page_config(page_title="Extractor de informacion de cursos Canvas", page_icon=":book:", layout="wide")
st.title("Extractor de informacion de cursos Canvas 📚")

course_ids_input = st.text_area("Ingrese IDs de cursos:", placeholder="Ej: 123, 456 789\n101112")

if st.button("Extraer información"):
    if not course_ids_input or not API_TOKEN:
        st.error("Debe ingresar los IDs de cursos y el API Token para continuar.")
    else:
        course_ids = parse_input(course_ids_input)
        resultados = []
        for course_id in course_ids:
            course_data = canvas_request(session, "get", f"/courses/{course_id}")
            if not course_data:
                resultados.append({
                    "Tipo": "❌ Error",
                    "Cuenta": "No disponible",
                    "Nombre": f"❌ Error al obtener curso {course_id}",
                    "ID Dictación": course_id,
                    "ID Plantilla": "No disponible",
                    "Estado": "No disponible",
                    "Progreso": "No disponible",
                    "Código": "No disponible",
                    "F. Inicio": "No disponible",
                    "F. Cierre": "No disponible",
                    "Modalidad": "No disponible",
                    "Link": f"{config('CLEAN_URL')}/courses/{course_id}",
                    "Profesor": "No disponible",
                    "Email Profesor": "No disponible",
                    "Director": "No disponible",
                    "Email Director": "No disponible",
                    "Email Tutor": "No disponible",
                })
                continue

            subaccount_data = canvas_request(session, "get", f"/accounts/{course_data.get('account_id')}")
            if not subaccount_data:
                resultados.append({
                    "Tipo": "❌ Error",
                    "Cuenta": "No disponible",
                    "Nombre": f"⚠️ Subcuenta no disponible para {course_id}",
                    "ID Dictación": course_id,
                    "ID Plantilla": "No disponible",
                    "Estado": "No disponible",
                    "Progreso": "No disponible",
                    "Código": "No disponible",
                    "F. Inicio": "No disponible",
                    "F. Cierre": "No disponible",
                    "Modalidad": "No disponible",
                    "Link": f"{config('CLEAN_URL')}/courses/{course_id}",
                    "Profesor": "No disponible",
                    "Email Profesor": "No disponible",
                    "Director": "No disponible",
                    "Email Director": "No disponible",
                    "Email Tutor": "No disponible",
                })
                continue
            course_data = canvas_request(session, "get", f"/courses/{course_id}")
            if not course_data:
                st.error(f"❌ No se pudo obtener datos del curso {course_id}.")
                continue
            subaccount_data = canvas_request(session, "get", f"/accounts/{course_data.get('account_id')}")
            if not subaccount_data:
                st.error(f"⚠️ No se pudo obtener la subcuenta del curso {course_id}.")
                continue
            blueprint_data = canvas_request(session, "get", f"/courses/{course_id}/blueprint_subscriptions")

            # Información básica del curso
            nombre_curso = course_data.get("name", "")
            subaccount_name = subaccount_data.get("name", "Sin información")
            course_code = course_data.get("course_code", "Sin información")
            sis_course_id = course_data.get("sis_course_id", "Sin información")
            link = f"{config('CLEAN_URL')}/courses/{course_id}"
            course_type = "Diplomado" if "Diplomado" in subaccount_name else "Magíster" if "Magíster" in subaccount_name else "Otro"
            estado = "🟢Publicado" if course_data.get("workflow_state") == "available" else "🔴No Publicado"
            
            #Sacar blueprint
            try:
                blueprint_course = (blueprint_data or [{}])[0].get("blueprint_course", {})
                blueprint_id = blueprint_course.get("id", "Sin información")
            except (IndexError, AttributeError):
                blueprint_id = "Sin información"
            
            # Fecha de inicio
            start_date_raw = course_data.get("start_at")
            if start_date_raw:
                start_date_datetime = datetime.strptime(start_date_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
                local_start_date = start_date_datetime.astimezone(santiago)
                start_date = local_start_date.strftime("%d-%m-%Y")
            else:
                start_date = "Sin información"
                local_start_date = None

            # Fecha de término (según último assignment con due date)
            assignments = canvas_request(session, "get", f"/courses/{course_id}/assignments")
            assignments_with_due = [a for a in assignments if a.get('due_at')]

            if assignments_with_due:
                latest_assignment = max(
                    assignments_with_due,
                    key=lambda a: datetime.strptime(a['due_at'], "%Y-%m-%dT%H:%M:%SZ")
                )
                end_date_raw = latest_assignment.get("due_at", "Sin información")
                if end_date_raw != "Sin información":
                    end_date_datetime = datetime.strptime(end_date_raw, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=utc)
                    local_end_date = end_date_datetime.astimezone(santiago)
                    end_date = local_end_date.strftime("%d-%m-%Y")
                else:
                    end_date = "Sin información"
                    local_end_date = None
            else:
                end_date = "Sin información"
                local_end_date = None

            # Cálculo del Progreso
            progreso = "Sin información"
            hoy = datetime.now(santiago).date()  # Fecha local Chile

            if local_start_date and local_end_date:
                fecha_inicio = local_start_date.date()
                fecha_fin = local_end_date.date()

                if hoy < fecha_inicio:
                    progreso = "🟡No iniciado"
                elif fecha_inicio <= hoy <= fecha_fin:
                    total_dias = (fecha_fin - fecha_inicio).days
                    dias_transcurridos = (hoy - fecha_inicio).days
                    porcentaje = (dias_transcurridos / total_dias) * 100 if total_dias > 0 else 100
                    progreso = f"🟢En progreso ({porcentaje:.1f}%)"
                elif hoy > fecha_fin:
                    progreso = "🔴Terminado"
            else:
                progreso = "🟠No Configurado"
            
            # Modalidad
            parts = sis_course_id.split("-")
            code = parts[1][:2]
            if code == "DM":
                modalidad = "Masivo"
            elif code[0] == "D":
                modalidad = "Nacional"
            else:
                modalidad = "Otro tipo"
                
            #Enrollments importantes
            enrollments = canvas_request(session, "get", f'/courses/{course_id}/enrollments/?type[]=TeacherEnrollment&type[]=TaEnrollment', paginated=True)
            profesor = "No asignado"
            profesor_email = "No asignado"
            director = "No asignado"
            director_email = "No asignado"
            tutor_social = "No asignado"
            tutor_social_email = "No asignado"
            for enrollment in enrollments:
                role = enrollment.get("role", "").lower()
                if role == "teacherenrollment":
                    profesor = enrollment.get("user", {}).get("name", "No disponible")
                    profesor_email = enrollment.get("user", {}).get("login_id", "No disponible")
                elif "director" in role:
                    director = enrollment.get("user", {}).get("name", "No disponible")
                    director_email = enrollment.get("user", {}).get("login_id", "No disponible")
                elif "tutor" in role:
                    #tutor_social = enrollment.get("user", {}).get("name", "No disponible")
                    tutor_social_email = enrollment.get("user", {}).get("login_id", "No disponible")
            
            resultados.append({
                "Tipo": course_type,
                "Cuenta": subaccount_name,
                "Nombre": nombre_curso,
                "ID Dictación": course_id,
                "ID Plantilla": blueprint_id,
                "Estado": estado,
                "Progreso": progreso,
                "Código": course_code,
                #"Sis ID": sis_course_id,
                "F. Inicio": start_date,
                "F. Cierre":end_date,
                "Modalidad": modalidad,
                "Link": link,
                "Profesor": profesor,
                "Email Profesor": profesor_email,
                "Director": director,
                "Email Director": director_email,
                "Email Tutor": tutor_social_email,
            })
        
        if resultados:
            df = pd.DataFrame(resultados)
            st.dataframe(df)
        else:
            st.write("No se encontró información para los cursos ingresados.")
