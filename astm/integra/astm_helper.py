from astm.integra.records import *

class ASTMHelper:
    @staticmethod
    def create_header_record(block_code):
        header_record = HeaderRecord()
        header_record.info_code = str(block_code)
        header_record.name = 'Cobas Integra'
        return header_record

    @staticmethod
    def create_order_records(booking_id, tests, sample_type, rack, pos, pri):
        record_id = OrderIDRecord()
        record_id.id = booking_id
        record_id.date = '02/04/2017'
        record_id.sample_type = sample_type
        record_info = OrderInfoRecord()
        record_info.rack = rack
        record_info.pos = pos
        record_info.pri = pri
        order_records = [record_id, record_info]
        for test in tests:
            test_record = TestIDRecord()
            test_record.id = test
            order_records.append(test_record)
        return order_records

    # @staticmethod
    # def create_patient_record(patient_id):
    #     record = CustomPatientRecord()
    #     record.laboratory_id = patient_id
    #     return record

class ASTMTestOrderCreator:
    @staticmethod
    def create_test_order(block_code, patient_id, booking_tests_dict):
        header_record = ASTMHelper.create_header_record(block_code)
        #patient_record = ASTMHelper.create_patient_record(patient_id)
        records = dict(header=header_record,data=[])
        for booking_id, booking_record in booking_tests_dict.items():
            order_records = ASTMHelper.create_order_records(booking_record.order, [23], booking_record.sample_type,booking_record.rack,
                                                            booking_record.pos, 'A')
            records['data'] = order_records
        return records