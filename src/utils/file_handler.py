import os
import json
import pickle


class FileIOHelper:
    @staticmethod
    def dump_json(obj, file_name, encoding="utf-8", indent=4):
        with open(file_name, "w", encoding=encoding) as fw:
            json.dump(
                obj, fw, indent=indent, default=FileIOHelper.handle_non_serializable
            )

    @staticmethod
    def handle_non_serializable(obj):
        return "non-serializable contents"  # mark the non-serializable part

    @staticmethod
    def load_json(file_name, encoding="utf-8"):
        with open(file_name, "r", encoding=encoding) as fr:
            return json.load(fr)

    @staticmethod
    def write_str(s, path):
        with open(path, "w") as f:
            f.write(s)

    @staticmethod
    def load_str(path):
        with open(path, "r") as f:
            return "\n".join(f.readlines())

    @staticmethod
    def dump_pickle(obj, path):
        with open(path, "wb") as f:
            pickle.dump(obj, f)

    @staticmethod
    def load_pickle(path):
        with open(path, "rb") as f:
            return pickle.load(f)


def dump_pickle(obj, path):
    with open(path, "wb") as f:
        pickle.dump(obj, f)


def load_pickle(path):
    with open(path, "rb") as f:
        return pickle.load(f)


def write_str(s, path):
    with open(path, "w") as f:
        f.write(s)


def load_str(path, encoding="utf-8"):
    with open(path, "r", encoding=encoding) as f:
        return "\n".join(f.readlines())


def handle_non_serializable(obj):
    return "non-serializable contents"  # mark the non-serializable part


def load_json(source, encoding="utf-8"):
    from_file = os.path.exists(source)
    if from_file:
        with open(source, "r", encoding=encoding) as f:
            return json.load(f)
    else:  # source is a dict_str
        return json.loads(source)


def dump_json(obj, path, ensure_ascii=True, indent=4):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=indent, ensure_ascii=ensure_ascii)


def pretify_json_(path):
    data = load_json(path)
    output_path = path.replace(".json", "_pretty.json")
    dump_json(data, output_path)


def pretify_json(path):
    output_path = path.replace(".json", "_pretty.json")

    try:
        data = load_json(path)
        with open(output_path, "w") as outfile:
            json.dump(data, outfile, indent=4, ensure_ascii=False)
    except json.JSONDecodeError:
        with open(path, "r") as infile:
            lines = infile.readlines()
            pretty_json = []
            for line in lines:
                try:
                    data = json.loads(line)
                    pretty_json.append(data)
                except json.JSONDecodeError as e:
                    print(f"Skipping line due to error: {e}")

        with open(output_path, "w") as outfile:
            for item in pretty_json:
                json.dump(item, outfile, indent=4, ensure_ascii=False)
                outfile.write("\n")


def read_yaml(file_path):
    with open(file_path, "r") as f:
        return yaml.safe_load(f)


def write_html(obj, path):
    with open(path, "w") as f:
        f.write(obj)
