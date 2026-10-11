import re

from django.http import FileResponse, HttpResponse, StreamingHttpResponse
from django.utils.http import content_disposition_header


def _read_range(file_handle, length, chunk_size=64 * 1024):
    remaining = length
    try:
        while remaining:
            chunk = file_handle.read(min(chunk_size, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
    finally:
        file_handle.close()


def protected_media_response(request, media_file, *, content_type, filename, as_attachment=False):
    file_handle = media_file.open('rb')
    file_handle.seek(0, 2)
    file_size = file_handle.tell()
    range_header = request.headers.get('Range', '').strip()
    match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header, re.IGNORECASE)

    if not match or not any(match.groups()):
        file_handle.seek(0)
        response = FileResponse(
            file_handle,
            content_type=content_type,
            as_attachment=as_attachment,
            filename=filename,
        )
        response['Accept-Ranges'] = 'bytes'
        return response

    start_text, end_text = match.groups()
    if start_text:
        start = int(start_text)
        end = int(end_text) if end_text else file_size - 1
    else:
        suffix_length = int(end_text)
        start = max(file_size - suffix_length, 0)
        end = file_size - 1

    if start >= file_size or end < start or file_size == 0:
        file_handle.close()
        response = HttpResponse(status=416, content_type=content_type)
        response['Content-Range'] = f'bytes */{file_size}'
        response['Accept-Ranges'] = 'bytes'
        return response

    end = min(end, file_size - 1)
    response_length = end - start + 1
    file_handle.seek(start)
    response = StreamingHttpResponse(
        _read_range(file_handle, response_length),
        status=206,
        content_type=content_type,
    )
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(response_length)
    response['Content-Range'] = f'bytes {start}-{end}/{file_size}'
    disposition = content_disposition_header(as_attachment, filename)
    if disposition:
        response['Content-Disposition'] = disposition
    return response
