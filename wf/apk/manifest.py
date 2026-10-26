"""Small read-only binary Android manifest identity reader (no SDK subprocess)."""
import struct


def _strings(data, start, header, size):
    count, _, flags, offset, _ = struct.unpack_from("<IIIII", data, start + 8)
    offsets = struct.unpack_from(f"<{count}I", data, start + header)
    result = []
    for item in offsets:
        position = start + offset + item
        def length(width):
            nonlocal position
            value = int.from_bytes(data[position:position + width], "little")
            position += width
            high = 1 << (width * 8 - 1)
            if value & high:
                value = ((value & (high - 1)) << (width * 8)) | int.from_bytes(
                    data[position:position + width], "little")
                position += width
            return value
        if flags & 0x100:
            length(1)
            count_bytes = length(1)
            encoding = "utf-8"
        else:
            count_bytes = length(2) * 2
            encoding = "utf-16-le"
        if position + count_bytes > start + size:
            raise ValueError("manifest string exceeds string pool")
        result.append(data[position:position + count_bytes].decode(encoding))
    return result


def _identity(data):
    """Return actual package/version attributes from the root manifest element."""
    if len(data) < 8 or struct.unpack_from("<H", data)[0] != 3:
        raise ValueError("APK manifest must be binary Android XML")
    if struct.unpack_from("<I", data, 4)[0] != len(data):
        raise ValueError("manifest declared length differs")
    position, strings = 8, []
    while position < len(data):
        kind, header, size = struct.unpack_from("<HHI", data, position)
        if header < 8 or size < header or position + size > len(data):
            raise ValueError("invalid manifest chunk")
        if kind == 1:
            strings = _strings(data, position, header, size)
        elif kind == 0x102:
            name = struct.unpack_from("<I", data, position + 20)[0]
            if strings[name] != "manifest":
                raise ValueError("manifest root element not found")
            start, step, count = struct.unpack_from("<HHH", data, position + 24)
            if step < 20:
                raise ValueError("invalid manifest attribute size")
            attrs = {}
            for index in range(count):
                at = position + 16 + start + index * step
                if at + 20 > position + size:
                    raise ValueError("manifest attributes exceed chunk")
                namespace, key, raw, _, zero, value_type, value = struct.unpack_from("<IIIHBBI", data, at)
                key = strings[key]
                if key in {"package", "versionCode", "versionName"}:
                    expected_ns = None if key == "package" else "http://schemas.android.com/apk/res/android"
                    actual_ns = None if namespace == 0xFFFFFFFF else strings[namespace]
                    if expected_ns != actual_ns or key in attrs or zero:
                        raise ValueError("ambiguous manifest identity attribute")
                    attrs[key] = strings[value] if value_type == 3 else value
            if not isinstance(attrs.get("package"), str) or type(attrs.get("versionCode")) is not int:
                raise ValueError("manifest package/versionCode missing")
            return {"package_name": attrs["package"], "versionCode": attrs["versionCode"],
                    "versionName": attrs.get("versionName")}
        position += size
    raise ValueError("manifest identity not found")


def identity(data):
    try:
        return _identity(data)
    except (IndexError, struct.error, UnicodeError) as error:
        raise ValueError("invalid binary Android manifest: " + type(error).__name__) from error
