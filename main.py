from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter
import pytesseract
from pdf2image.pdf2image import convert_from_path
import re
from datetime import datetime
import fnmatch
import typer
import streamlit as st


REGEX_PO = re.compile(r"(4|5)50\d{7}|ENQA\s?\d{4}")


# VERIFIER SI LE FICHIER EST SCANNE OU NATIF
def check_pdf_type(file):
    pdf_checker = PdfReader(file)
    page_text = pdf_checker.pages[0].extract_text()
    if page_text == "":
        return True
    return False
    

# RECUPERATION DE LA DATE DE CREATION
def get_date(pdf_file):
    creation_date_raw = datetime.fromtimestamp(pdf_file.stat().st_mtime)
    creation_date = creation_date_raw.strftime("%Y%m%d")
    return creation_date


# RECUPERATION DU NOMBRE DE PAGES
def get_pages(pdf_file):
    reader = PdfReader(pdf_file)
    return len(reader.pages)


# FONCTION POUR SAUVEGARDER LES FICHIERS DANS UN DOSSIER CHOISI
def save_uploaded_file(file, path):
    with open(path / file.name, 'wb') as f:
        f.write(file.getbuffer())
    return st.success(f'File saved successfully: {file.name}')


# INTERFACE STREAMLIT
st.title("Rename .pdf files")
st.markdown("---")
output_folder = Path(st.text_input(label="Select output folder"))
uploaded_files = st.file_uploader("Select files to rename", type="pdf", accept_multiple_files=True)

with st.form(key='MyApp'):

    if uploaded_files is not None:
        for file in uploaded_files:
            save_uploaded_file(file, output_folder)

    pdf_files_list = [file for file in output_folder.iterdir() if (file.is_file() and file.suffix == ".pdf")]


    def convert_btn_func():

        for file in pdf_files_list:

            pdf_reader = PdfReader(file) #création du reader pdf
            date = get_date(file) #récupération de la date de création

            # si on a un fichier scanné
            if check_pdf_type(file):
                # si le nombre de pages == 1 : pas besoin de splitter le document, on renomme juste dans un premier temps avec la date
                if get_pages(file) == 1:
                    new_file_name = f'{date}_{file.stem}_{file.suffix}'
                    #on crée un nouveau fichier avec ce nouveau nom
                    new_file_path = output_folder.joinpath(new_file_name)
                    file.rename(new_file_path)
                # si le nombre de pages > 1, il faut splitter et ensuite renommer chaque page avec la date de création.
                else:
                    with open(file, 'rb') as input_file:
                        pdf_reader = PdfReader(file)
                        for num_page in range(len(pdf_reader.pages)):
                            #pour chaque page on créée un writer pdf
                            pdf_writer = PdfWriter()
                            #on ajoute la page au writer
                            pdf_writer.add_page(pdf_reader.pages[num_page])
                            #on créée un nouveau nom
                            new_file_name = f'{date}_{file.stem}_{num_page + 1}{file.suffix}'
                            #on crée un nouveau fichier avec ce nouveau nom
                            new_file_path = output_folder.joinpath(new_file_name)
                            with open(new_file_path, 'wb') as output_file:
                                pdf_writer.write(output_file)
                    file.unlink()
            # si on a un fichier natif
            else:
                new_file_name = f'{date}_{file.stem}{file.suffix}'
                new_file_path = output_folder.joinpath(new_file_name)
                file.rename(new_file_path)

            
        # on refait une nouvelle liste avec les nouveaux fichiers issus du split, et on va ensuite lancer le script ocr pour décrypter le contenu de l'image
        pdf_list_after_splitting = [file for file in output_folder.iterdir() if (file.is_file() and file.suffix.lower() == ".pdf")]

        new_list = [] #nouvelle liste servant à gérer les doublons des noms de fichiers

        for file in pdf_list_after_splitting:
            #si fichier pdf scanné:
            if check_pdf_type(file) == True: 
                images = convert_from_path(file, 500)
                text_result = ''
                for pageNum, imgBlob in enumerate(images):
                    img_to_text = pytesseract.image_to_string(imgBlob, lang='eng')
                    text_result += img_to_text
                PO_list = sorted([i.group(0) for i in re.finditer(REGEX_PO, text_result)])
                PO_list_str = "_".join(set(PO_list))
                if PO_list_str == "":
                    new_file_name = f"{file.stem[:8]}_ERREUR_COMMANDE"
                else:
                    new_file_name = f"{file.stem[:8]}_{PO_list_str}"
                new_list.append(new_file_name)
                # on va compter à chaque fois qu'on ajoute le nom de fichier à la liste afin de récupérer un numéro qui sera unique, et servira donc de numérotation en cas de doublons, afin d'éviter les erreurs de renommage.
                existing_files = [i for i in fnmatch.filter(new_list, new_file_name)]
                final_filename = f"{new_file_name}_{len(existing_files)}{file.suffix}"
                new_file_path = output_folder.joinpath(final_filename)
                file.rename(new_file_path)
                if "ERREUR_COMMANDE" in new_file_name:
                    typer.secho(f"File {file.name} has not been correctly renamed --> No PO number found --> {final_filename}", fg=typer.colors.RED)
                    st.error(f"File {file.name} has not benn correctly renamed --> No PO number found --> {final_filename}")
                else:
                    typer.secho(f"File {file.name} has successfully been renamed --> {final_filename}", fg=typer.colors.GREEN)
                    st.success(f"File {file.name} has successfully been renamed --> {final_filename} ")
            #si fichier pdf natif:
            elif check_pdf_type(file) == False:
                reader = PdfReader(file)
                list_pages = reader.pages
                full_pdf_text = ''
                for page in list_pages:
                    text = page.extract_text()
                    full_pdf_text += text
                PO_list = sorted([i.group(0) for i in re.finditer(REGEX_PO, full_pdf_text)])
                PO_list_str = "_".join(set(PO_list))
                if PO_list_str == "":
                    new_file_name = f"{file.stem[:8]}_ERREUR_COMMANDE"
                else:
                    new_file_name = f"{file.stem[:8]}_{PO_list_str}"
                new_list.append(new_file_name)
                # on va compter à chaque fois qu'on ajoute le nom de fichier à la liste afin de récupérer un numéro qui sera unique, et servira donc de numérotation en cas de doublons, afin d'éviter les erreurs de renommage.
                existing_files = [i for i in fnmatch.filter(new_list, new_file_name)]
                final_filename = f"{new_file_name}_{len(existing_files)}{file.suffix}"
                new_file_path = output_folder.joinpath(final_filename)
                file.rename(new_file_path)  
                if "ERREUR_COMMANDE" in new_file_name:
                    typer.secho(f"File {file.name} has not been correctly renamed --> No PO number found --> {final_filename}", fg=typer.colors.RED)
                    st.error(f"File {file.name} has not benn correctly renamed --> No PO number found --> {final_filename}")
                else:
                    typer.secho(f"File {file.name} has successfully been renamed --> {final_filename}", fg=typer.colors.GREEN)
                    st.success(f"File {file.name} has successfully been renamed --> {final_filename} ")


    convert_btn = st.form_submit_button("Process files")

if convert_btn:
    convert_btn_func()