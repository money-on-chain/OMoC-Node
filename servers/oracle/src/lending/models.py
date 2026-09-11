from peewee import (
    AutoField,
    BooleanField,
    CharField,
    DatabaseProxy,
    IntegerField,
    Model,
    TextField,
)

database_proxy = DatabaseProxy()


class BaseModel(Model):
    class Meta:
        database = database_proxy


class LendingVault(BaseModel):
    chain_id = IntegerField()
    user = CharField()
    tp_token = CharField()
    moc_bucket = CharField()
    ac_balance = TextField()
    credit_units = TextField()
    liquidating = BooleanField()
    event_block = IntegerField()
    event_block_hash = CharField()
    transaction_index = IntegerField()
    log_index = IntegerField()
    generation = IntegerField(default=1)

    class Meta:
        table_name = "lending_vaults"
        indexes = (
            (("chain_id", "user", "tp_token", "moc_bucket"), True),
            (("chain_id", "tp_token", "moc_bucket", "credit_units"), False),
        )


class LendingEvent(BaseModel):
    id = AutoField()
    chain_id = IntegerField()
    transaction_hash = CharField()
    log_index = IntegerField()
    block_number = IntegerField()
    block_hash = CharField()
    user = CharField()
    tp_token = CharField()
    moc_bucket = CharField()
    previous_state = TextField(null=True)
    new_state = TextField()

    class Meta:
        table_name = "lending_events"
        indexes = ((('chain_id', 'transaction_hash', 'log_index'), True),)


class LendingBlock(BaseModel):
    chain_id = IntegerField()
    block_number = IntegerField()
    block_hash = CharField()
    parent_hash = CharField(null=True)

    class Meta:
        table_name = "lending_blocks"
        indexes = ((('chain_id', 'block_number'), True),)


class LendingCursor(BaseModel):
    chain_id = IntegerField()
    manager = CharField()
    deployment_block = IntegerField()
    last_projected_block = IntegerField()
    last_projected_hash = CharField()
    schema_version = IntegerField(default=1)

    class Meta:
        table_name = "lending_cursor"
        indexes = ((('chain_id', 'manager'), True),)


MODELS = [LendingVault, LendingEvent, LendingBlock, LendingCursor]
