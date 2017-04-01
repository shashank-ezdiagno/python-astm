from collections import Iterable
from ..compat import unicode
from ..mapping import Record
from ..constants import (
    SOH, STX, ETX, ETB, CR, LF, CRLF, EOT, EOTLF, ETXLF, ENCODING
)
from .record_type import RecordType, RECORD_FIELDS_LENGTH_MAP
from enum import IntEnum
try:
    from itertools import izip_longest
except ImportError:  # Python 3
    from itertools import zip_longest as izip_longest

class DataType(IntEnum):
    MESSAGE = 0
    BLOCK_HEADER = 1
    BLOCK_DATA = 2
    BLOCK_CS = 3
    RECORD = 4

class Separators:
    def __init__(self, field, record, component=None, repeat=None):
        self.FIELD_SEP = field
        self.RECORD_SEP = record
        self.COMPONENT_SEP = component
        self.REPEAT_SEP = repeat

DEFAULT_SEPARATORS = Separators(b'_', LF)

class CodecIntegraHelper:
    @staticmethod
    def is_message(data):
        if data.startswith(SOH) and data.endswith(EOTLF):
            return True
        return False

    @staticmethod
    def is_block_header(data):
        if not data.startswith(SOH):
            return False
        line_code = data[2:2]
        if line_code != b'09':
            return False
        return True

    @staticmethod
    def is_block_data(data):
        if CodecIntegraHelper.is_block_header(data) or not data.startswith(STX) or not data.endswith(ETXLF):
            return False
        return True

    @staticmethod
    def is_block_cs(data):
        byte = data[:1].decode()
        if  byte.isdigit() and (byte == '0' or byte == '1'):
            return True
        return False

    @staticmethod
    def make_checksum(data, encoding):
        print('make_checksum',data)
        value = 0
        for byte in data:
            value += byte
        return str(value % 1000).encode(encoding)

    @staticmethod
    def remove_checksum(data):
        last_index = data.rfind(LF)
        return data[:last_index + 1]

class CodecIntegra:
    def __init__(self, separators=DEFAULT_SEPARATORS, encoding=ENCODING, block_check_enabled = True, dateformat = "%d/%m/%Y", timeformat="%H:%M:%S"):
        self.RECORD_SEP = separators.RECORD_SEP
        self.FIELD_SEP = separators.FIELD_SEP
        self.COMPONENT_SEP = separators.COMPONENT_SEP
        self.REPEAT_SEP = separators.REPEAT_SEP
        self.encoding = encoding
        self.block_check_enabled = block_check_enabled
        self.dateformat = dateformat
        self.timeformat = timeformat

    def decode(self,data):
        """Common Integra decoding function that tries to guess which kind of data it
        handles.

        If `data` starts with SOH character (``0x02``) than probably it is
        full Integra message with checksum and other system characters.

        If `data` starts with digit character (``0-9``) than probably it is
        frame of records leading by his sequence number. No checksum is expected
        in this case.

        Otherwise it counts `data` as regular record structure.

        Note, that `data` should be bytes, not unicode string even if you know his
        `encoding`.

        :param data: Integra data object.
        :type data: bytes

        :param encoding: Data encoding.
        :type encoding: str

        :return: List of Integra records with unicode data.
        :rtype: list
        """
        if not isinstance(data, bytes):
            raise TypeError('bytes expected, got %r' % data)
        if CodecIntegraHelper.is_message(data):  # may be decode message \x02...\x03CS\r\n
            records = self.decode_message(data)
            return records
        if CodecIntegraHelper.is_block_header(data):
            header_record = self.decode_header(data)
            return dict(header=header_record)
        if CodecIntegraHelper.is_block_data(data):
            data_records = self.decode_data(data)
            return dict(data=data_records)
        if CodecIntegraHelper.is_block_cs(data):
            cs_record = self.decode_cs(data)
            return dict(cs=cs_record)
        return dict(data=[decode_record(data)])


    def decode_message(self, message):
        """Decodes complete Integra message that is sent or received due
        communication routines. It should contains checksum that would be
        additionally verified.

        :param message: Integra message.
        :type message: bytes

        :param encoding: Data encoding.
        :type encoding: str

        :returns: Tuple of three elements:

            * :class:`int` frame sequence number.
            * :class:`list` of records with unicode data.
            * :class:`bytes` checksum.

        :raises:
            * :exc:`ValueError` if Integra message is malformed.
            * :exc:`AssertionError` if checksum verification fails.
        """
        if not isinstance(message, bytes):
            raise TypeError('bytes expected, got %r' % message)
        if not (message.startswith(SOH) and message.endswith(EOTLF)):
            raise ValueError('Malformed Integra message. Expected that it will started'
                             ' with %x and followed by %x%x characters. Got: %r'
                             ' ' % (ord(STX), ord(EOT), ord(LF), message))
        blocks = message[2:-2]
        print('blocks', blocks)
        blocks_arr = blocks.split(LF)
        print('blocks_arr', blocks_arr)
        header_block = LF.join([SOH,blocks_arr[0]])
        print('header_block', header_block)
        data_block = blocks_arr[1:-3]
        print('data_block', data_block)
        cs_block = blocks_arr[-3:-1]
        print('cs_block', cs_block)
        cs_record = None
        if not self.block_check_enabled:
            data_block = blocks_arr[1:]
        else:
            message_with_checksum = message[:-3]
            message_without_checksum = CodecIntegraHelper.remove_checksum(message_with_checksum)
            cs = CodecIntegraHelper.make_checksum(message_without_checksum, self.encoding)
            cs_block = LF.join(cs_block)
            cs_record = self.decode_cs(cs_block, cs)
        data_block = LF.join(data_block)
        header_record = self.decode_header(header_block)
        data_records = self.decode_data(data_block)
        return dict(header=header_record, data = data_records, cs = cs_record)

    def decode_header(self, data):
        header_data = data[2:]
        fields = self.decode_record(header_data)
        return fields

    def decode_data(self, data):
        data_data = data[2:-2]
        print(data, data_data)
        if not data_data:
            return None
        return [self.decode_record(record)
                 for record in data_data.split(self.RECORD_SEP)]

    def decode_cs(self, data, cs):
        cs_data = data.split(LF)
        print(data,cs_data)
        ccs = cs_data[1]
        assert cs == ccs, 'Checksum failure: expected %r, calculated %r' % (cs, ccs)
        return list([data.decode(self.encoding) for data in cs_data])

    def decode_record(self, data):
        fields = []
        # for item in data.split(self.FIELD_SEP):
        #     item = item.decode(self.encoding)
        #     fields.append([None, item][bool(item)])
        if not data:
            return fields
        line_code = int(data[:2])
        record_type = RecordType(line_code)
        field_lengths = RECORD_FIELDS_LENGTH_MAP[record_type]
        cur_pos = 0
        fields = []
        for field_length in field_lengths:
            field = data[cur_pos:cur_pos + field_length].decode(self.encoding)
            cur_pos += field_length + 1
            fields.append(field)
        return fields

    def encode(self, records, sc=0, size=None):
        msg = self.encode_message(records, sc)
        if size is not None and len(msg) > size:
            return list(split(msg, size))
        return [msg]

    def encode_message(self, records, sc=0):
        """Encodes Integra message.

        :param records: List of Integra records.
        :type records: list

        :param sc: sequence counter
        :type sc: int

        :return: Integra complete message with checksum and other control characters.
        :rtype: str
        """
        data_block = self.RECORD_SEP.join(self.encode_record(record)
                               for record in records.get('data',[]))

        header_block = self.encode_record(records['header'])
        data = b''.join([SOH, LF, header_block, LF, STX, LF, data_block, ETXLF])
        print(data)
        if self.block_check_enabled:
            data = b''.join([data, str(sc).encode(self.encoding), LF])
            data = b''.join([data, CodecIntegraHelper.make_checksum(data, self.encoding), LF])
        data = b''.join([data, EOT, LF])
        return data

    def encode_record(self, record):
        from datetime import datetime, time
        """Encodes single Integra record.

        :param record: Integra record. Each :class:`str`-typed item counted as field
                       value, one level nested :class:`list` counted as components
                       and second leveled - as repeated components.
        :type record: list

        :returns: Encoded Integra record.
        :rtype: str
        """
        if isinstance(record, Record):
            record = record.to_astm()
        fields = []
        _append = fields.append
        for field in record:
            if isinstance(field, bytes):
                _append(field)
            elif isinstance(field, unicode):
                _append(field.encode(self.encoding))
            elif isinstance(field, datetime):
                _append(field.strftime(self.dateformat).encode(encoding))
            elif isinstance(field, time):
                _append(field.strftime(self.timeformat).encode(encoding))
            elif field is None:
                _append(b'')
            else:
                _append(unicode(field).encode(encoding))
        return self.FIELD_SEP.join(fields)






