import inspect
from functools import wraps
from typing import Iterable, TypeVar, Optional, Type, List

from schematics import Model
from schematics.common import NOT_NONE
from schematics.types import UUIDType, StringType, ModelType, ListType, DateType, BaseType, DictType, BooleanType
from schematics.exceptions import DataError
from schematics.types.base import TypeMeta
from flask import abort, request, Response, jsonify


# Inheriting this class will make an enum exhaustive
class EnumMeta(TypeMeta):
    def __new__(mcs, name, bases, attrs):
        attrs['choices'] = [v for k, v in attrs.items() if not k.startswith('_') and k.isupper()]
        return TypeMeta.__new__(mcs, name, bases, attrs)


class ApproxDateType(DateType):
    formats = ['%Y-%m']


# Intentionally non-exhaustive
class DemoResultType(StringType):
    ANY = 'ANY'

    # Errors
    ERROR_INVALID_CREDENTIALS = 'ERROR_INVALID_CREDENTIALS'
    ERROR_ANY_PROVIDER_MESSAGE = 'ERROR_ANY_PROVIDER_MESSAGE'
    ERROR_CONNECTION_TO_PROVIDER = 'ERROR_CONNECTION_TO_PROVIDER'

    # Document verification specific
    ERROR_UNSUPPORTED_DOCUMENT_TYPE = 'ERROR_UNSUPPORTED_DOCUMENT_TYPE'
    DOCUMENT_IMAGE_CHECK_FAILURE = 'DOCUMENT_IMAGE_CHECK_FAILURE'
    DOCUMENT_FORGERY_CHECK_FAILURE = 'DOCUMENT_FORGERY_CHECK_FAILURE'
    DOCUMENT_NAME_FIELD_DIFFERENT = 'DOCUMENT_NAME_FIELD_DIFFERENT'
    DOCUMENT_NAME_FIELD_UNREADABLE = 'DOCUMENT_NAME_FIELD_UNREADABLE'
    DOCUMENT_DOB_FIELD_DIFFERENT = 'DOCUMENT_DOB_FIELD_DIFFERENT'
    DOCUMENT_DOB_FIELD_UNREADABLE = 'DOCUMENT_DOB_FIELD_UNREADABLE'
    DOCUMENT_ALL_PASS = 'DOCUMENT_ALL_PASS'


# Local field names (for errors)
class Field(StringType):
    DOB = 'DOB'
    ADDRESS_HISTORY = 'ADDRESS_HISTORY'
    GIVEN_NAMES = 'GIVEN_NAMES'
    FAMILY_NAME = 'FAMILY_NAME'
    DOCUMENT = 'DOCUMENT'


class CommercialRelationshipType(StringType, metaclass=EnumMeta):
    PASSFORT = 'PASSFORT'
    DIRECT = 'DIRECT'


class ErrorType(StringType, metaclass=EnumMeta):
    INVALID_CREDENTIALS = 'INVALID_CREDENTIALS'
    INVALID_CONFIG = 'INVALID_CONFIG'
    MISSING_CHECK_INPUT = 'MISSING_CHECK_INPUT'
    INVALID_CHECK_INPUT = 'INVALID_CHECK_INPUT'
    PROVIDER_CONNECTION = 'PROVIDER_CONNECTION'
    PROVIDER_MESSAGE = 'PROVIDER_MESSAGE'
    UNSUPPORTED_DEMO_RESULT = 'UNSUPPORTED_DEMO_RESULT'


class GenderType(StringType, metaclass=EnumMeta):
    MALE = 'M'
    FEMALE = 'F'


class AddressType(StringType, metaclass=EnumMeta):
    STRUCTURED = 'STRUCTURED'


class ErrorSubType(StringType, metaclass=EnumMeta):
    # INVALID_CHECK_INPUT
    UNSUPPORTED_COUNTRY = 'UNSUPPORTED_COUNTRY'


class EntityType(StringType, metaclass=EnumMeta):
    INDIVIDUAL = 'INDIVIDUAL'


# Only including individual document types at this time
class DocumentCategory(StringType, metaclass=EnumMeta):
    PROOF_OF_ADDRESS = 'PROOF_OF_ADDRESS'
    PROOF_OF_BANK_ACCOUNT = 'PROOF_OF_BANK_ACCOUNT'
    PROOF_OF_IDENTITY = 'PROOF_OF_IDENTITY'
    PROOF_OF_SOURCE_OF_FUNDS = 'PROOF_OF_SOURCE_OF_FUNDS'
    PROOF_OF_SOURCE_OF_WEALTH = 'PROOF_OF_SOURCE_OF_WEALTH'
    PROOF_OF_TAX_STATUS = 'PROOF_OF_TAX_STATUS'


class DocumentType(StringType, metaclass=EnumMeta):
    BIOMETRIC_STATE_ID = 'BIOMETRIC_STATE_ID'
    DRIVING_LICENCE = 'DRIVING_LICENCE'
    FACE_IMAGE = 'FACE_IMAGE'
    PASSPORT = 'PASSPORT'
    PASSPORT_CARD = 'PASSPORT_CARD'
    STATE_ID = 'STATE_ID'
    VOTER_ID = 'VOTER_ID'


class DocumentImageType(StringType, metaclass=EnumMeta):
    BACK = 'BACK'
    FACE = 'FACE'
    FRONT = 'FRONT'


class CheckedDocumentField(StringType, metaclass=EnumMeta):
    FIELD_ADDRESS = 'FIELD_ADDRESS'
    FIELD_DOB = 'FIELD_DOB'
    FIELD_EXPIRY = 'FIELD_EXPIRY'
    FIELD_FAMILYNAME = 'FIELD_FAMILYNAME'
    FIELD_GENDER = 'FIELD_GENDER'
    FIELD_GIVENNAMES = 'FIELD_GIVENNAMES'
    FIELD_ISSUED = 'FIELD_ISSUED'
    FIELD_ISSUINGCOUNTRY = 'FIELD_ISSUINGCOUNTRY'
    FIELD_MRZ = 'FIELD_MRZ'
    FIELD_NATIONALITY = 'FIELD_NATIONALITY'
    FIELD_NUMBER  = 'FIELD_NUMBER'


class CheckedDocumentFieldResult(StringType, metaclass=EnumMeta):
    CHECK_INVALID = 'CHECK_INVALID'
    CHECK_UNCERTAIN = 'CHECK_UNCERTAIN'
    CHECK_VALID = 'CHECK_VALID'


class DecisionClass(StringType, metaclass=EnumMeta):
    ERROR = 'ERROR'
    FAIL = 'FAIL'
    PARTIAL = 'PARTIAL'
    PASS = 'PASS'
    WARN = 'WARN'


class ProviderConfig(Model):
    require_dob = BooleanType(required=True)
    require_address = BooleanType(required=True)

    class Options:
        export_level = NOT_NONE


class ProviderCredentials(Model):
    username = StringType(required=True)
    password = StringType(required=True)
    url = StringType(required=True)
    public_key = StringType(required=True)
    private_key = StringType(required=True)

    class Options:
        export_level = NOT_NONE


class Error(Model):
    type = ErrorType(required=True)
    sub_type = ErrorSubType()
    message = StringType(required=True)
    data = DictType(StringType(), default=None)

    @staticmethod
    def unsupported_country():
        return Error({
            'type': ErrorType.INVALID_CHECK_INPUT,
            'sub_type': ErrorSubType.UNSUPPORTED_COUNTRY,
            'message': 'Country not supported.',
        })

    @staticmethod
    def missing_required_field(field: str):
        return Error({
            'type': ErrorType.MISSING_CHECK_INPUT,
            'data': {
                'field': field,
            },
            'message': f'Missing required field ({field})',
        })

    @staticmethod
    def missing_documents():
        return Error({
            'type': ErrorType.INVALID_CHECK_INPUT,
            'message': 'At least one document must be submitted for validation',
        })

    class Options:
        export_level = NOT_NONE


class Warn(Model):
    type = ErrorType(required=True)
    message = StringType(required=True)

    class Options:
        export_level = NOT_NONE


class FullName(Model):
    title = StringType(default=None)
    given_names = ListType(StringType(), default=None)
    family_name = StringType(min_length=1, default=None)

    class Options:
        export_level = NOT_NONE


class StructuredAddress(Model):
    country = StringType(required=True)
    state_province = StringType(default=None)
    county = StringType(default=None)
    postal_code = StringType(default=None)
    locality = StringType(default=None)
    postal_town = StringType(default=None)
    route = StringType(default=None)
    street_number = StringType(default=None)
    premise = StringType(default=None)
    subpremise = StringType(default=None)
    address_lines = ListType(StringType(), default=None)

    class Options:
        export_level = NOT_NONE


class Address(StructuredAddress):
    type = AddressType(required=True, default=AddressType.STRUCTURED)
    original_freeform_address = StringType(default=None)
    original_structured_address: Optional[StructuredAddress] = ModelType(StructuredAddress, default=None)


class DatedAddress(Model):
    address: Address = ModelType(Address, required=True)
    start_date = ApproxDateType(default=None)
    end_date = ApproxDateType(default=None)

    class Options:
        export_level = NOT_NONE


class PersonalDetails(Model):
    name: Optional[FullName] = ModelType(FullName, default=None)
    dob = StringType(default=None)
    nationality = StringType(default=None)
    national_identity_number = DictType(StringType(), default=None)
    gender = GenderType(default=None)

    class Options:
        export_level = NOT_NONE


class FieldCheckResult(Model):
    field = CheckedDocumentField(default=None)
    result = CheckedDocumentFieldResult(default=None)

    class Options:
        export_level = NOT_NONE


class DocumentCheck(Model):
    category = StringType(default=None)
    result = DecisionClass(default=None)
    type = StringType(default=None)

    class Options:
        export_level = NOT_NONE


class DocumentResult(Model):
    all_passed = BooleanType(default=None)
    document_type_passed = BooleanType(default=None)
    error_reason = StringType(default=None)
    field_checks: Optional[List[FieldCheckResult]] = ListType(ModelType(FieldCheckResult), default=None)
    forgery_checks: Optional[List[DocumentCheck]] = ListType(ModelType(DocumentCheck), default=None)
    forgery_checks_passed = BooleanType(default=None)
    image_checks: Optional[List[DocumentCheck]] = ListType(ModelType(DocumentCheck), default=None)
    image_checks_passed = BooleanType(default=None)
    provider_name = StringType(default=None)

    class Options:
        export_level = NOT_NONE


# Extracted data from a verified document
class DocumentData(Model):
    address_history: Optional[List[DatedAddress]] = ListType(ModelType(DatedAddress), default=None)
    expiry = DateType(default=None)
    external_ref = StringType(default=None)
    external_service = StringType(default=None)
    issued = DateType(default=None)
    issuer = StringType(default=None)
    issuing_country = StringType(default=None)
    mrz1 = StringType(default=None)
    mrz2 = StringType(default=None)
    mrz3 = StringType(default=None)
    number = StringType(default=None)
    personal_details: Optional[PersonalDetails] = ModelType(PersonalDetails, default=None)
    result: Optional[DocumentResult] = ModelType(DocumentResult, default=None)

    class Options:
        export_level = NOT_NONE


# This represents only a 'DocumentImageResourceCase3', i.e. the variant that only
# contains a UUID and doesn't have the image data internally
class DocumentImageResource(Model):
    document_category = DocumentCategory(default=None)
    document_type = DocumentType(default=None)
    id = UUIDType(required=True)
    image_type = DocumentImageType(default=None)
    upload_date = DateType(default=None)

    class Options:
        export_level = NOT_NONE


class Document(Model):
    category = DocumentCategory(required=True)
    document_type = DocumentType(required=True)
    extracted_data: Optional[DocumentData] = ModelType(DocumentData, default=None)
    id = UUIDType(required=True)
    images: List[DocumentImageResource] = ListType(ModelType(DocumentImageResource))
    verification_result: Optional[DocumentResult] = ModelType(DocumentResult, default=None)

    class Options:
        export_level = NOT_NONE
    
    def get_images(self) -> List[DocumentImageResource]:
        return self.images or []


class IndividualData(Model):
    entity_type = EntityType(required=True, default=EntityType.INDIVIDUAL)
    personal_details: Optional[PersonalDetails] = ModelType(PersonalDetails, default=None)
    address_history: Optional[List[DatedAddress]] = ListType(ModelType(DatedAddress), default=None)
    documents: Optional[List[Document]] = ListType(ModelType(Document), default=None)

    class Options:
        export_level = NOT_NONE

    def get_current_address(self) -> Optional[Address]:
        if self.address_history:
            return self.address_history[-1].address
        else:
            return None

    def get_dob(self) -> Optional[str]:
        return self.personal_details and self.personal_details.dob

    def get_given_names(self) -> Optional[List[str]]:
        return self.personal_details and self.personal_details.name and self.personal_details.name.given_names

    def get_family_name(self) -> Optional[str]:
        return self.personal_details and self.personal_details.name and self.personal_details.name.family_name

    def get_documents(self) -> List[Document]:
        return self.documents or []
    
    def get_document_image_ids(self):
        return [img.id for doc in self.get_documents() for img in doc.get_images()]


# Passfort -> Integration
class RunCheckRequest(Model):
    id = UUIDType(required=True)
    demo_result = DemoResultType(default=None)
    commercial_relationship = CommercialRelationshipType(required=True)
    check_input: IndividualData = ModelType(IndividualData, required=True)
    provider_config: ProviderConfig = ModelType(ProviderConfig, required=True)
    provider_credentials: Optional[ProviderCredentials] = ModelType(ProviderCredentials, default=None)

    class Options:
        export_level = NOT_NONE


# Integration -> Passfort
class RunCheckResponse(Model):
    provider_id = UUIDType(required=True)
    reference = StringType(default=None)

    custom_data = DictType(BaseType, required=True)
    errors: List[Error] = ListType(ModelType(Error), default=[])
    warnings: List[Warn] = ListType(ModelType(Warn), default=[])
    provider_data = BaseType(required=False)

    @staticmethod
    def error(errors: List[Error]) -> 'RunCheckResponse':
        res = RunCheckResponse()
        res.errors = errors
        return res


# Callback Notification -> Passfort
class CallbackRequest(Model):
    provider_id = UUIDType(required=True)
    reference = StringType(default=None)

    custom_data = DictType(BaseType, required=True)


# Passfort -> Requests data notified as ready in CallbackRequest
class FinishRequest(Model):
    id = UUIDType(required=True)
    reference = StringType(required=True)

    custom_data = DictType(BaseType, required=True)


class FinishResponse(Model):
    check_output: Optional[IndividualData] = ModelType(IndividualData, default=None)
    result: StringType(default=None)
    errors: List[Error] = ListType(ModelType(Error), default=[])
    warnings: List[Warn] = ListType(ModelType(Warn), default=[])
    provider_data = BaseType(required=True)


# Passfort -> Requests download of raw image data
class DownloadImageRequest(Model):
    check_id = UUIDType(required=True)
    image_reference = StringType(required=True)

    commercial_relationship = CommercialRelationshipType(required=True)
    provider_config: ProviderConfig = ModelType(ProviderConfig, required=True)
    provider_credentials: Optional[ProviderCredentials] = ModelType(ProviderCredentials, default=None)

    custom_data = DictType(BaseType, required=True)


# Validation
T = TypeVar('T')


def _first(x: Iterable[T]) -> Optional[T]:
    return next(iter(x), None)


def _get_input_annotation(signature: inspect.Signature) -> Optional[Type[Model]]:
    first_param: Optional[inspect.Parameter] = _first(signature.parameters.values())
    if first_param is None:
        return None

    if first_param.kind not in [inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD]:
        return None

    if not issubclass(first_param.annotation, Model):
        return None

    return first_param.annotation


def validate_models(fn):
    """
    Creates a Schematics Model from the request data and validates it.

    Throws DataError if invalid.
    Otherwise, it passes the validated request data to the wrapped function.
    """

    signature = inspect.signature(fn)

    output_model = signature.return_annotation
    input_model = _get_input_annotation(signature)

    if issubclass(output_model, Response):
        raw_output = True
    elif issubclass(signature.return_annotation, Model):
        raw_output = False
    else:
        raise AssertionError(
            'Must have a return type annotation which is a subclass of either '
            '`schematics.Model` or `flask.Response`'
        )

    @wraps(fn)
    def wrapped_fn(*args, **kwargs):
        if input_model is None:
            res = fn(*args, **kwargs)
        else:
            model = None
            try:
                model = input_model().import_data(request.json, apply_defaults=True)
                model.validate()
            except DataError as e:
                abort(Response(str(e), status=400))

            res = fn(model, *args, **kwargs)

        assert isinstance(res, output_model)

        if raw_output:
            return res
        else:
            return jsonify(res.serialize())

    return wrapped_fn

