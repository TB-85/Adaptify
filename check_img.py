import struct

def get_image_info(file_path):
    with open(file_path, 'rb') as f:
        data = f.read(24)
        if data[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = struct.unpack('>LL', data[16:24])
            print(f'PNG width: {w}, height: {h}')
        else:
            print('Not a valid PNG')

get_image_info('frontend/www/logo_icon.png')
