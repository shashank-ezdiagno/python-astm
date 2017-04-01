from ..mapping import AbsoluteFloatingField, ASCIIFloatingField, FixedLengthIntegerField, \
                        FixedLengthTextField, DateField, Record, TimeField, ConstantField


HeaderRecord = Record.build(
    ConstantField(name='code', default='14'),
    FixedLengthTextField(name='name', length=16),
    FixedLengthIntegerField(name='info_code', length=2)
)



ResultDataRecord = Record.build(
    ConstantField(name='code', default='00'),
    ASCIIFloatingField(name="value", length=13),
    FixedLengthTextField(name="unit", length=6),
    FixedLengthIntegerField(name='flagX', length=3),
    FixedLengthIntegerField(name='flagS', length=3, default=0),
    FixedLengthIntegerField(name='flagCalc', length=3),
    FixedLengthIntegerField(name='flagQC', length=3),
    ASCIIFloatingField(name="range_value", length=13),
)

ResultTimeRecord = Record.build(
    ConstantField(name='code', default='01'),
    TimeField(name='time', format='%H:%M:%S'),
)

QueryResultRecord = Record.build(
    ConstantField(name='code', default='10'),
    FixedLengthIntegerField(name='type', length=2)
)

QueryOrderRecord =  Record.build(
    ConstantField(name='code', default='40'),
    FixedLengthIntegerField(name='type', length=1)
)

SlotStateRecord400 = Record.build(
    ConstantField(name='code', default='41'),
    FixedLengthIntegerField(name='racknum1', length=3),
    FixedLengthIntegerField(name='racknum2', length=3),
    FixedLengthIntegerField(name='racknum3', length=3),
    FixedLengthIntegerField(name='racknum4', length=3),
    FixedLengthIntegerField(name='racknum5', length=3),
    FixedLengthIntegerField(name='racknum6', length=3)
)

TubeInfoRecord = Record.build(
    ConstantField(name='code', default='42'),
    FixedLengthIntegerField(name='rack', length=3),
    FixedLengthIntegerField(name='pos', length=2),
    FixedLengthIntegerField(name='type', length=1),
    FixedLengthTextField(name='order', length=15),
    FixedLengthTextField(name='sample_type', length=3)
)

PatientIDRecord = Record.build(
    ConstantField(name='code', default='50'),
    FixedLengthTextField(name='id', length=15)
)

PatientInfoRecord = Record.build(
    ConstantField(name='code', default='51'),
    DateField(name='dob', format="%d/%m/%Y"),
    FixedLengthTextField(name='sex', length=1),
    FixedLengthTextField(name='name', length=31),
    FixedLengthTextField(name='text2', length=21),
    FixedLengthTextField(name='text3', length=21)
)

OrderIDRecord = Record.build(
    ConstantField(name='code', default='53'),
    FixedLengthTextField(name='id', length=15),
    DateField(name='date', format="%d/%m/%Y"),
    FixedLengthTextField(name='sample_type', length=3)
)

OrderInfoRecord = Record.build(
    ConstantField(name='code', default='54'),
    FixedLengthIntegerField(name='rack', length=3),
    FixedLengthIntegerField(name='pos', length=2),
    FixedLengthTextField(name='pri', length=1),
    FixedLengthTextField(name='text1', length=21),
    FixedLengthTextField(name='text2', length=21),
)

TestIDRecord = Record.build(
    ConstantField(name='code', default='55'),
    FixedLengthIntegerField(name='id', length=3)
)

ErrorRecord = Record.build(
    ConstantField(name='code', default='96'),
    FixedLengthTextField(name='id', length=2)
)

