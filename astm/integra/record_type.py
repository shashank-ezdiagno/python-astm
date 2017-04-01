from enum import IntEnum


class RequestBlockType(IntEnum):
    SynBlock = 0
    PatientEntry = 40,
    PatientModification = 42,
    PatientDeletion = 41,
    OrderEntry = 10,
    OrderDeletion = 11,
    OrderQueryRequest = 60,
    ResultRequest = 9,

class ResponseBlockType(IntEnum):
    IdleBlock = 0,
    OrderManipulationResponse = 19,
    ResultResponse = 4,
    ErrorBlock = 8,
    PatientManipulationResponse = 49,
    PendingSamples = 62,
    OrderQueryResponse = 61,
    OrderStatusResponse = 69

class RecordType(IntEnum):
    Header = 14,
    ResultData = 0,
    ResultTime = 1,
    QueryResult = 10,
    QueryOrder = 40,
    SlotState400 = 41,
    TubeInfo = 42,
    PatientID = 50,
    PatientInfo=51,
    OrderID = 53,
    OrderInfo=54,
    TestID=55,
    Error=96

RECORD_FIELDS_LENGTH_MAP = {
        RecordType.Header: [2, 16, 2],
        RecordType.ResultData: [2, 13, 6, 3, 3, 3, 3, 13],
        RecordType.ResultTime: [2, 8],
        RecordType.QueryResult: [2, 2],
        RecordType.QueryOrder: [2, 1],
        RecordType.SlotState400: [2, 3, 3, 3, 3, 3, 3],
        RecordType.TubeInfo: [2, 3, 2, 1, 15, 3],
        RecordType.PatientID: [2, 15],
        RecordType.PatientInfo: [2, 10, 1, 31, 21, 21],
        RecordType.OrderID: [2, 15, 10, 3],
        RecordType.OrderInfo: [2, 3, 2, 1, 21, 21],
        RecordType.TestID: [2, 3],
        RecordType.Error: [2, 2]
    }