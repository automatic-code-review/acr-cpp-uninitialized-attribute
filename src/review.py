import hashlib
import json
import os
import subprocess


def review(config):
    path_source = config['path_source']

    comments = []

    for raiz, _, arquivos in os.walk(path_source):
        for arquivo in arquivos:
            if arquivo.endswith('.h'):
                header_path = os.path.join(raiz, arquivo)
                comments.extend(review_by_file(header_path, path_source))

    return comments


def ler_linhas_do_arquivo(nome_arquivo, linha_inicio, linha_fim):
    conteudo_linhas = []

    if linha_inicio is None:
        return conteudo_linhas, 0, 0

    with open(nome_arquivo, 'r') as arquivo:
        linhas = arquivo.readlines()

        if linha_fim is None:
            linha_fim = len(linhas)

        indice_inicio = max(0, linha_inicio - 1)
        indice_fim = min(len(linhas), linha_fim)

        for i in range(indice_inicio, indice_fim):
            if linhas[i].strip():
                conteudo_linhas.append(linhas[i])

    return conteudo_linhas, linha_inicio, linha_fim


def get_attrs(header_file):
    data = subprocess.run(
        'ctags --output-format=json --languages=c++ --fields=+an ' + header_file,
        shell=True,
        capture_output=True,
        text=True,
    ).stdout

    attrs = []
    constructor_name = None

    for data_obj in data.split('\n'):
        if data_obj == '':
            continue

        data_obj = json.loads(data_obj)

        if data_obj['kind'] != 'member':
            continue

        if 'constexpr' in data_obj['pattern'] or 'static' in data_obj['pattern'] or "::__anon" in data_obj['scope']:
            continue

        if constructor_name is None:
            class_name = data_obj['scope']
            constructor_name = f"{class_name}::{class_name}"

        atr_name = data_obj['name']
        attrs.append(atr_name)

    return attrs, constructor_name


def get_content(source_file, constructor_name):
    data = subprocess.run(
        'ctags --output-format=json --languages=c++ --fields=+an -n ' + source_file,
        shell=True,
        capture_output=True,
        text=True,
    ).stdout

    objts = []

    for data_obj in data.split('\n'):
        if data_obj == '':
            continue

        obj_json = json.loads(data_obj)

        if 'scope' not in obj_json:
            continue

        objts.append(obj_json)

    objts = sorted(objts, key=lambda x: x['line'])

    end_line = None
    start_line = None

    for index, data_obj in enumerate(objts):
        if constructor_name in data_obj['pattern']:
            start_line = data_obj['line'] + 1
            end_line = index + 1

            if end_line >= len(objts):
                end_line = None
            else:
                end_line = objts[end_line]['line'] - 1

            break

    if start_line is None:
        with open(source_file, 'r') as arquivo:
            linhas = arquivo.readlines()

            for index, linha in enumerate(linhas):
                if linha.startswith(constructor_name):
                    start_line = index + 1

                    for data_obj in objts:
                        method_start_line = data_obj['line']
                        if method_start_line > start_line:
                            end_line = method_start_line - 1
                            break

                    break

    return ler_linhas_do_arquivo(source_file, start_line, end_line)


def review_by_file(header_file, path_root):
    attrs, constructor_name = get_attrs(header_file)

    if len(attrs) == 0:
        return []

    comments = []
    source_file = header_file.replace(".h", ".cpp")

    if not os.path.exists(source_file):
        return comments

    content, linha_inicio, linha_fim = get_content(source_file, constructor_name)
    attrs_not_found = []

    for attr in attrs:
        found = False

        for myLine in content:
            if f'{attr}' in myLine.replace(" ", ""):
                found = True

        if not found:
            attrs_not_found.append(attr)

    if len(attrs_not_found) > 0:
        attr_to_comment = '<br>'.join(attrs_not_found)
        header_relative = header_file.replace(path_root, "")[1:]
        descr_comment = f'O arquivo `{header_relative}` possui os seguintes atributos sem inicializacao no ' \
                        f'constructor<br><br>{attr_to_comment}<br><br>Constructor name: {constructor_name}' \
                        f'<br>Linha inicio: {linha_inicio}<br>Linha fim: {linha_fim}'

        comments.append(__create_comment(descr_comment, header_relative))

    return comments


def __create_comment(message, path):
    comment = {
        "id": __generate_md5(f"{path}-{message}"),
        "comment": message.replace("${FILE_PATH}", path),
        "position": {
            "path": path,
            "snipset": False,
            "startInLine": 1
        }
    }

    return comment


def __generate_md5(string):
    md5_hash = hashlib.md5()
    md5_hash.update(string.encode('utf-8'))
    return md5_hash.hexdigest()
