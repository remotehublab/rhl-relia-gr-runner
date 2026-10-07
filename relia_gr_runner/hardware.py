"""Read-only radio discovery before advertising a runner to the scheduler."""
import ctypes
import ctypes.util
import socket


def radio_ready(config):
    pluto = config.get('ADALM_PLUTO_IP_ADDRESS')
    if pluto:
        # A listening TCP port alone does not establish that the AD9361 exists.
        address = pluto.removeprefix('ip:')
        try:
            with socket.create_connection((address, 30431), timeout=2):
                pass
            lib = ctypes.CDLL(ctypes.util.find_library('iio') or 'libiio.so.0')
            lib.iio_create_network_context.argtypes = [ctypes.c_char_p]
            lib.iio_create_network_context.restype = ctypes.c_void_p
            lib.iio_context_find_device.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
            lib.iio_context_find_device.restype = ctypes.c_void_p
            lib.iio_context_destroy.argtypes = [ctypes.c_void_p]
            context = lib.iio_create_network_context(address.encode())
            if not context:
                return False
            try:
                return bool(lib.iio_context_find_device(context, b'ad9361-phy'))
            finally:
                lib.iio_context_destroy(context)
        except (OSError, ValueError):
            return False
    redpitaya = config.get('RED_PITAYA_IP_ADDRESS')
    if redpitaya:
        try:
            with socket.create_connection((redpitaya, 1001), timeout=2):
                return True
        except OSError:
            return False
    return False
