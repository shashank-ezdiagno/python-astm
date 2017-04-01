# -*- coding: utf-8 -*-
#
# Copyright (C) 2013 Alexander Shorin
# All rights reserved.
#
# This software is licensed as described in the file COPYING, which
# you should have received as part of this distribution.
#

import logging
import socket
from ..asynclib import loop
from .codec import CodecIntegra, Separators, CodecIntegraHelper, DEFAULT_SEPARATORS
from ..records import RecordsHelper
from .records import *
from .record_type import RecordType, ResponseBlockType
from .astm_helper import ASTMTestOrderCreator
from ..constants import ENQ, EOT, ENCODING
from ..exceptions import NotAccepted
from ..mapping import Record
from ..protocol import ASTMProtocol
from ..constants import LF

log = logging.getLogger(__name__)

__all__ = ['Client', 'Emitter']

class RecordsStateMachine(object):
    """Simple state machine to track emitting ASTM records in right order.
    """
    def __init__(self):
        self.state = {}

    def __call__(self, new_record):
        if new_record is not None:
            assert self.is_acceptable(new_record),\
                   'invalid state %r, expected one of: %r' \
                   % (self.state, new_record)
            if 'cs' in new_record:
                self.state = {}
        self.state.update(new_record)

    def is_acceptable(self, new_record):
        if not self.state:
            return True
        keys = list(new_record.keys())
        if len(keys) > 1:
            return False
        key = keys[0]
        if key == 'header':
            return key not in self.state
        return True

class Emitter(object):
    """ASTM records emitter for :class:`Client`.

    Used as wrapper for user provided one to provide proper routines around for
    sending Header and Terminator records.

    :param emitter: Generator/coroutine.

    :param encoding: Data encoding.
    :type encoding: str

    :param flow_map: Records flow map. Used by :class:`RecordsStateMachine`.
    :type: dict

    :param chunk_size: Chunk size in bytes. If :const:`None`, emitter record
                       wouldn't be split into chunks.
    :type chunk_size: int

    :param bulk_mode: Sends all records for single session (starts from Header
                      and ends with Terminator records) via single message
                      instead of sending each record separately. If result
                      message is too long, it may be split by chunks if
                      `chunk_size` is not :const:`None`. Keep in mind, that
                      collecting all records for single session may take some
                      time and server may reject data by timeout reason.
    :type bulk_mode: bool
    """

    #: Records state machine controls emitting records in right order. It
    #: receives `records_flow_map` as only argument on Emitter initialization.
    state_machine = RecordsStateMachine

    def __init__(self, emitter, separators, encoding,
                 chunk_size=None, bulk_mode=False, block_check_enabled=True, dateformat="%d/%m/%Y", timeformat="%H:%M:%S"):
        self._emitter = emitter()
        self._is_active = False
        self.encoding = encoding
        self.records_sm = self.state_machine()
        # flag to signal that user's emitter produces no records
        self.empty = False
        self.buffer = []
        self.chunk_size = chunk_size
        self.bulk_mode = bulk_mode
        self.block_check_enabled = block_check_enabled
        self.encoder = CodecIntegra(DEFAULT_SEPARATORS or separators, encoding, block_check_enabled, dateformat, timeformat)

    def _get_record(self, value=None):
        record = self._emitter.send(value if self._is_active else None)
        if not self._is_active:
            self._is_active = True
        try:
            self.records_sm(record)
        except Exception as err:
            self.throw(type(err), err.args)
        key = list(record.keys())[0]
        record = record[key]
        if isinstance(record, Record):
            record = record.to_astm()
        return {key:record}

    def _send_record(self, record, sc):
        if self.bulk_mode:
            records = record
            while True:
                record = self._get_record(True)
                print(record)
                is_block_cs = 'cs' in record
                print('is_block_cs', is_block_cs)
                if is_block_cs:
                    if self.block_check_enabled:
                        records.update(record)
                    break
                else:
                    if 'header' in record:
                        records.update(record)
                    else:
                        records['data'] = records.get('data', [])
                        records['data'].append(record['data'])
            chunks = self.encoder.encode(records, sc,  self.chunk_size)
        else:
            chunks = self.encoder.encode(record, sc,
                            self.chunk_size)

        self.buffer.extend(chunks)
        data = self.buffer.pop(0)
        return data

    def send(self, value=None, sc = 0):
        """Passes `value` to the emitter. Semantically acts in same way as
        :meth:`send` for generators.

        If the emitter has any value within local `buffer` the returned value
        will be extracted from it unless `value` is :const:`False`.

        :param value: Callback value. :const:`True` indicates that previous
                      record was successfully received and accepted by server,
                      :const:`False` signs about his rejection.
        :type value: bool

        :return: Next record data to send to server.
        :rtype: bytes
        """
        if self.buffer and value:
            return self.buffer.pop(0)
        record = self._get_record(value)
        print(record)
        return self._send_record(record, sc)

    def throw(self, exc_type, exc_val=None, exc_tb=None):
        """Raises exception inside the emitter. Acts in same way as
        :meth:`throw` for generators.

        If the emitter had catch an exception and return any record value, it
        will be proceeded in common way.
        """
        record = self._emitter.throw(exc_type, exc_val, exc_tb)
        if record is not None:
            return self._send_record(record)

    def close(self):
        """Closes the emitter. Acts in same way as :meth:`close` for generators.
        """
        self._emitter.close()

class BaseRecordsDispatcher(object):
    """Abstract dispatcher of received ASTM records by :class:`RequestHandler`.
    You need to override his handlers or extend dispatcher for your needs.
    For instance::

        class Dispatcher(BaseRecordsDispatcher):

            def __init__(self, encoding=None):
                super(Dispatcher, self).__init__(encoding)
                # extend it for your needs
                self.dispatch['M'] = self.my_handler
                # map custom wrappers for ASTM records to their type if you
                # don't like to work with raw data.
                self.wrapper['M'] = MyWrapper

            def on_header(self, record):
                # initialize state for this session
                ...

            def on_patient(self, record):
                # handle patient info
                ...

            # etc handlers

            def my_handler(self, record):
                # handle custom record that wasn't implemented yet by
                # python-astm due to some reasons
                ...

    After defining our dispatcher, we left only to let :class:`Server` use it::

        server = Server(dispatcher=Dispatcher)
    """

    #: Encoding of received messages.
    encoding = ENCODING
    log = logging.getLogger('astm.server.dispatcher')

    def __init__(self, encoding=None):
        self.encoding = encoding or self.encoding
        self.dispatch = {
            RecordType.Header: self.on_header,
            RecordType.ResultData: self.on_result_data,
            RecordType.ResultTime: self.on_result_time,
            RecordType.SlotState400: self.on_slot_state_400,
            RecordType.TubeInfo: self.on_tube_info,
            RecordType.PatientID: self.on_patient_id,
            RecordType.PatientInfo: self.on_patient_info,
            RecordType.OrderID: self.on_order_id,
            RecordType.OrderInfo: self.on_order_info,
            RecordType.TestID: self.on_test_id,
            RecordType.Error: self.on_error
        }
        self.wrappers = {
            RecordType.Header: HeaderRecord,
            RecordType.ResultData: ResultDataRecord,
            RecordType.ResultTime:ResultTimeRecord,
            RecordType.SlotState400: SlotStateRecord400,
            RecordType.TubeInfo: TubeInfoRecord,
            RecordType.PatientID: PatientIDRecord,
            RecordType.PatientInfo: PatientInfoRecord,
            RecordType.OrderID: OrderIDRecord,
            RecordType.OrderInfo: OrderInfoRecord,
            RecordType.TestID: TestIDRecord,
            RecordType.Error: ErrorRecord
        }
        self.block_type = ResponseBlockType.IdleBlock
        self.context = {}

    def handle_message(self, message):
        decoder = CodecIntegra()
        records = decoder.decode_message(message)
        self.log.info('Dispatcher: %r', records)
        records['data'] = records['data'] or []
        recordslist = [records['header']] + records['data']
        for record in recordslist:
            line_code = int(record[0])
            self.log.info('Record: %r', record)
            record_type = RecordType(line_code)
            self.dispatch.get(record_type, self.on_unknown)(self.wrap(record))
        message = self.on_message_end()
        sc = (int(records['cs'][0]) + 1) % 2
        return sc, self.block_type, message


    def wrap(self, record):
        line_code = int(record[0])
        rtype = RecordType(line_code)
        if rtype in self.wrappers:
            return self.wrappers[rtype](*record)
        return record

    def on_header(self, record):
        header = record
        block_code = int(record.info_code)
        self.block_type = ResponseBlockType(block_code)
        self.log.info('block type: %r', self.block_type)
        self.log.info('Header: %r', record)

    def on_result_data(self, record):
        self.log.info('Result Data: %r', record)
        self.context['result'][self.context['cur_test']] = record

    def on_result_time(self, record):
        self.log.info('Result Time: %r', record)

    def on_slot_state_400(self, record):
        self.log.info('Slot State: %r', record)

    def on_tube_info(self, record):
        self.log.info('Tube Info: %r', record)
        if self.block_type == ResponseBlockType.PendingSamples:
            print('ghussa')
            self.context['samples'] = self.context.get('samples', {})
            self.context['samples'][record.order] = record

    def on_unknown(self, record):
        self.log.warn('Unknown record: %r', record)

    def on_patient_id(self, record):
        self.log.info('PatientID: %r', record)

    def on_patient_info(self, record):
        self.log.info('Patient Info: %r', record)

    def on_order_id(self, record):
        self.log.info('Order ID: %r', record)
        self.context['order_id'] = record.id

    def on_order_info(self, record):
        self.log.info('Order Info: %r', record)

    def on_test_id(self, record):
        self.log.info('Test ID: %r', record)
        if self.block_type == ResponseBlockType.ResultResponse:
            self.context['result'] = self.context.get('result', {})
            self.context['result'][record.id] = None
            self.context['cur_test'] = record.id


    def on_error(self, record):
        self.log.info('Error Info: %r', record)

    def on_message_end(self):
        self.log.info('Message End')
        message = None
        if self.block_type == ResponseBlockType.ResultResponse:
            order_id = self.context['order_id']
            records = [record for test_id, record in self.context['result'].items()]
            self.handle_result(records)
        elif self.block_type == ResponseBlockType.PendingSamples:
            message = self.handle_query(self.context['samples'])
        self.context = {}
        return message

    def handle_query(self, records_dict):
        order_creator = ASTMTestOrderCreator()
        records = order_creator.create_test_order(10, '100023', records_dict)
        return records

    def handle_result(self, records):
        self.log.info('Handle Result %r', records)






class Client(ASTMProtocol):
    """Common ASTM client implementation.

    :param emitter: Generator function that will produce ASTM records.
    :type emitter: function

    :param host: Server IP address or hostname.
    :type host: str

    :param port: Server port number.
    :type port: int

    :param timeout: Time to wait for response from server. If response wasn't
                    received, the :meth:`on_timeout` will be called.
                    If :const:`None` this timer will be disabled.
    :type timeout: int

    :param flow_map: Records flow map. Used by :class:`RecordsStateMachine`.
    :type: dict

    :param chunk_size: Chunk size in bytes. :const:`None` value prevents
                       records chunking.
    :type chunk_size: int

    :param bulk_mode: Sends all records for single session (starts from Header
                      and ends with Terminator records) via single message
                      instead of sending each record separately. If result
                      message is too long, it may be split by chunks if
                      `chunk_size` is not :const:`None`. Keep in mind, that
                      collecting all records for single session may take some
                      time and server may reject data by timeout reason.
    :type bulk_mode: bool

    Base `emitter` is a generator that yield ASTM records one by one preserving
    their order::

        from astm.records import (
            HeaderRecord, PatientRecord, OrderRecord, TerminatorRecord
        )
        def emitter():
            assert (yield HeaderRecord()), 'header was rejected'
            ok = yield PatientRecord(name={'last': 'foo', 'first': 'bar'})
            if ok:  # you also can decide what to do in case of record rejection
                assert (yield OrderRecord())
            yield TerminatorRecord()  # we may do not care about rejection

    :class:`Client` thought :class:`RecordsStateMachine` keep track
    on this order, raising :exc:`AssertionError` if it is broken.

    When `emitter` terminates with :exc:`StopIteration` or :exc:`GeneratorExit`
    exception client connection to server closing too. You may provide endless
    `emitter` by wrapping function body with ``while True: ...`` loop polling
    data from source from time to time. Note, that server may have communication
    timeouts control and may close session after some time of inactivity, so
    be sure that you're able to send whole session (started by Header record and
    ended by Terminator one) within limited time frame (commonly 10-15 sec.).
    """

    #: Wrapper of emitter to provide session context and system logic about
    #: sending head and tail data.
    emitter_wrapper = Emitter
    dispatcher = BaseRecordsDispatcher

    def __init__(self, emitter, host='localhost', port=15200,
                 encoding=None, timeout=20, separators=DEFAULT_SEPARATORS,
                 chunk_size=None, bulk_mode=False, block_check_enabled=True, dateformat="%d/%m/%Y", dispatcher=None):
        super(Client, self).__init__(timeout=timeout)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((host, port))
        self.is_sc_established = False
        self.emitter = self.emitter_wrapper(
            emitter,
            encoding=encoding or self.encoding,
            separators=separators,
            chunk_size=chunk_size,
            bulk_mode=bulk_mode,
            block_check_enabled=block_check_enabled,
            dateformat=dateformat
        )
        self.dispatcher = dispatcher or self.dispatcher
        self.terminator = 100

    def handle_connect(self):
        """Initiates ASTM communication session."""
        super(Client, self).handle_connect()
        self.is_sc_established = False
        self._open_session()

    def handle_close(self):
        self.emitter.close()
        #super(Client, self).handle_close()

    def _open_session(self):
        from .codec import CodecIntegra
        from .records import HeaderRecord
        codec = CodecIntegra(block_check_enabled=False)
        record = HeaderRecord()
        record.info_code = '00'
        record.name = 'Cobas Integra'
        data = dict(header=record.to_astm())
        data = codec.encode(data)
        print(data)
        for chunk in data:
            self.push(chunk)

    def _close_session(self, close_connection=False):
        log.info('closing session')
        #self.push(EOT)
        if close_connection:
            self.close_when_done()

    def run(self, timeout=1.0, *args, **kwargs):
        """Enters into the :func:`polling loop <astm.asynclib.loop>` to let
        client send outgoing requests."""
        loop(timeout, *args, **kwargs)

    def on_eot(self):
        """Raises :class:`NotAccepted` exception."""
        raise NotAccepted('Client should not receive EOT.')

    def on_enq(self):
        """Raises :class:`NotAccepted` exception."""
        raise NotAccepted('Client should not receive ENQ.')

    def on_message(self):
        """Raises :class:`NotAccepted` exception."""
        self.sc, block_type, message_result = self.dispatcher().handle_message(self._last_recv_data)
        try:
            if message_result:
                message = CodecIntegra().encode_message(message_result, self.sc)
                self.sc = (self.sc + 1) % 2
            else:
                message = self.emitter.send(True, self.sc)
        except StopIteration:
            self._close_session(True)
        else:
            self.push(message)

    def on_timeout(self):
        """Sends final EOT message and closes connection after his receiving."""
        super(Client, self).on_timeout()
        self._close_session(True)
