from __future__ import annotations

import base64
import binascii
import math
import re
import uuid
from datetime import datetime
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    field_validator,
    model_validator,
)


# ---------------------------------------------------------------------------
# Courses
# ---------------------------------------------------------------------------


class CourseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(..., min_length=1, max_length=255)
    semester: str = Field(..., min_length=1, max_length=50)


class CourseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(None, min_length=1, max_length=255)
    semester: str | None = Field(None, min_length=1, max_length=50)


class CourseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    semester: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------


class RosterEntryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    course_id: int
    netid: str
    full_name: str
    email: str
    is_active: bool
    imported_at: datetime


class RosterUploadResult(BaseModel):
    imported: int
    updated: int
    deactivated: int
    errors: list[str]


class RosterEntryPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool | None = None
    netid: str | None = Field(None, min_length=1, max_length=100)
    full_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None


class RosterRowIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    netid: str = Field(..., min_length=1, max_length=100)
    full_name: str = Field(..., min_length=1, max_length=255)
    email: str = Field(..., min_length=1, max_length=255)


class RosterImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[RosterRowIn] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Games
# ---------------------------------------------------------------------------


class GameCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(..., min_length=1, max_length=255)
    description: str = Field("", max_length=5000)
    max_players: int = Field(150, ge=1, le=500)
    course_id: int | None = None


class HostGameCreate(GameCreate):
    """POST /host/games — a host-created game must always be attached to a course."""

    course_id: int


class GameUpdate(BaseModel):
    """PUT /admin/games/{id}. course_id is accepted only while the stored value is NULL."""

    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    max_players: int | None = Field(None, ge=1, le=500)
    course_id: int | None = None


class HostGameUpdate(BaseModel):
    """PUT /host/games/{id}. Deliberately has no course_id: extra="forbid" makes a host
    attempt to re-point a game a 422, so course reassignment stays admin-only."""

    model_config = ConfigDict(extra="forbid")
    title: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=5000)
    max_players: int | None = Field(None, ge=1, le=500)


class GameResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    description: str
    max_players: int
    course_id: int | None
    course_name: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------


PIO_MIN_ITEMS = 3
PIO_MAX_ITEMS = 6
PIO_MAX_ITEM_LEN = 200


def _is_int_permutation(value: object, n: int) -> bool:
    """True if value is a list of real ints (bools excluded) forming a permutation of 0..n-1."""
    return (
        isinstance(value, list)
        and all(type(x) is int for x in value)
        and sorted(value) == list(range(n))
    )


def validate_put_in_order(grading_type: str, config: dict, answer_data: dict) -> None:
    """Structural checks for a put_in_order question; raises ValueError on the first failure.

    Shared by QuestionCreate.validate_structure and authoring_service.update_question (which
    validates the merged values, since QuestionUpdate only sees a partial body).
    """
    config = config or {}
    answer_data = answer_data or {}
    if set(config) != {"items"}:
        raise ValueError('Put in Order config may only contain "items"')
    items = config.get("items")
    if not isinstance(items, list) or not (
        PIO_MIN_ITEMS <= len(items) <= PIO_MAX_ITEMS
    ):
        raise ValueError("Put in Order needs between 3 and 6 items")
    if any(not isinstance(item, str) for item in items):
        raise ValueError("Every item must be text")
    stripped = [item.strip() for item in items]
    if any(not item for item in stripped):
        raise ValueError("Every item needs text")
    if any(len(item) > PIO_MAX_ITEM_LEN for item in stripped):
        raise ValueError("Each item must be at most 200 characters")
    if len({item.lower() for item in stripped}) != len(stripped):
        raise ValueError("Items must be different")
    has_order = "correct_order" in answer_data
    if grading_type == "ACCURACY" or has_order:
        order = answer_data.get("correct_order")
        if not _is_int_permutation(order, len(items)):
            raise ValueError(
                "Correct order is missing or invalid: it must list each item index exactly once"
            )
        if grading_type == "ACCURACY" and order == list(range(len(items))):
            raise ValueError("Display order must differ from the correct order")


def is_image_id(value: object) -> bool:
    """
    A library image id in canonical form: a lowercase, hyphenated UUID
    (docs/design-image-support.md section 3.3). MySQL compares CHAR ids
    case-insensitively but where-used compares in Python, so nothing else is allowed.
    """
    if not isinstance(value, str):
        return False
    try:
        return str(uuid.UUID(value)) == value
    except ValueError:
        return False


_OPTION_IMAGE_TYPES = ("multiple_choice", "multi_select")


def validate_image_keys(q_type: str, prompt_image_id: object, config: dict) -> None:
    """
    Where image references may appear (T8, design sections 3.2 and 3.3); raises
    ValueError naming the field. Pure structure: whether the ids exist and belong to
    the game's course is checked with the database by
    image_service.validate_question_images. Called from
    QuestionCreate.validate_structure and, on the merged values, from
    authoring_service.update_question, for every type.
    """
    config = config if isinstance(config, dict) else {}
    if prompt_image_id is not None:
        if not is_image_id(prompt_image_id):
            raise ValueError("prompt_image_id must be an image id")
        if q_type == "pin_the_spot":
            raise ValueError(
                "prompt_image_id: a Pin the Spot question can't have a prompt image; "
                "its canvas is the image"
            )
    if "option_image_ids" in config:
        if q_type not in _OPTION_IMAGE_TYPES:
            raise ValueError(
                "option_image_ids: only multiple choice and multi-select options can "
                "have images"
            )
        ids, options = config["option_image_ids"], config.get("options")
        if (
            not isinstance(ids, list)
            or not isinstance(options, list)
            or len(ids) != len(options)
        ):
            raise ValueError("option_image_ids must be a list as long as options")
        for i, image_id in enumerate(ids):
            if image_id is not None and not is_image_id(image_id):
                raise ValueError(f"option_image_ids[{i}] must be an image id or null")
    if "image_id" in config and q_type != "pin_the_spot":
        raise ValueError("image_id: only a Pin the Spot canvas can be a library image")


PTS_MAX_IMAGE_URL_LEN = 1_500_000
PTS_MAX_IMAGE_SIDE = 20_000
_PTS_DATA_URL = re.compile(r"^data:image/(png|jpeg|gif|webp);base64,", re.IGNORECASE)


def _is_real_number(value: object) -> bool:
    """A finite int/float that is not a bool (True is an int)."""
    return (
        type(value) in (int, float) and math.isfinite(value)  # type: ignore[arg-type]
    )


def _is_valid_image_url(url: object) -> bool:
    if not isinstance(url, str) or not url or len(url) > PTS_MAX_IMAGE_URL_LEN:
        return False
    if url[:8].lower() == "https://":
        if any(ch.isspace() for ch in url):
            return False
        try:
            return bool(urlsplit(url).netloc)
        except ValueError:
            return False
    match = _PTS_DATA_URL.match(url)
    if not match:
        return False
    payload = url[match.end() :]
    if not payload:
        return False
    try:
        base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        return False
    return True


def validate_pin_the_spot(grading_type: str, config: dict, answer_data: dict) -> None:
    """Structural checks for a pin_the_spot question; raises ValueError on the first failure.

    Shared by QuestionCreate.validate_structure and authoring_service.update_question (which
    validates the merged values, since QuestionUpdate only sees a partial body).
    """
    config = config or {}
    answer_data = answer_data if answer_data is not None else {}
    # Exactly one image source: a URL, or a course-library image (T8). With image_id
    # the client still sends the size, and the server overwrites it from the image
    # row (image_service.validate_question_images), then validates again.
    if not isinstance(config, dict) or set(config) not in (
        {"image_url", "image_width", "image_height"},
        {"image_id", "image_width", "image_height"},
    ):
        raise ValueError(
            'Pin the Spot config must contain "image_width", "image_height" and exactly '
            'one of "image_url" and "image_id"'
        )
    width, height = config["image_width"], config["image_height"]
    for side in (width, height):
        if type(side) is not int or not (1 <= side <= PTS_MAX_IMAGE_SIDE):
            raise ValueError(
                "Image width and height must be whole numbers from 1 to 20000"
            )
    if "image_id" in config:
        if not is_image_id(config["image_id"]):
            raise ValueError("image_id must be an image id")
    elif not _is_valid_image_url(config["image_url"]):
        raise ValueError(
            "Image must be an https:// URL or a base64 PNG, JPEG, GIF or WebP data: URL"
        )
    if not isinstance(answer_data, dict):
        raise ValueError("Pin the Spot answer_data must be an object")
    if answer_data == {}:
        if grading_type == "ACCURACY":
            raise ValueError("Place a target on the image")
        return
    if set(answer_data) != {"target", "r_full", "r_zero"}:
        raise ValueError(
            'Pin the Spot answer_data must contain exactly "target", "r_full" and "r_zero"'
        )
    target = answer_data["target"]
    if (
        not isinstance(target, dict)
        or set(target) != {"x", "y"}
        or not all(
            _is_real_number(target[k]) and 0 <= target[k] <= 1 for k in ("x", "y")
        )
    ):
        raise ValueError("Target must be {x, y} with numbers from 0 to 1")
    r_full, r_zero = answer_data["r_full"], answer_data["r_zero"]
    if not (_is_real_number(r_full) and _is_real_number(r_zero)):
        raise ValueError("Radii must be numbers")
    diagonal = math.sqrt(1 + (height / width) ** 2)
    if not (0 < r_full < r_zero <= diagonal):
        raise ValueError(
            "Radii must satisfy 0 < full-credit radius < zero-credit radius <= image diagonal"
        )


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(
        ...,
        pattern="^(multiple_choice|true_false|fill_in_the_blank|multi_select|put_in_order|pin_the_spot)$",
    )
    grading_type: str = Field(..., pattern="^(ACCURACY|COMPLETENESS)$")
    prompt: str = Field(..., min_length=1, max_length=2000)
    prompt_image_id: str | None = None
    config: dict = Field(default_factory=dict)
    answer_data: dict = Field(default_factory=dict)
    time_limit_seconds: int = Field(30, ge=2, le=300)
    points_value: float = Field(1.0, ge=0, le=100000)
    order_index: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_structure(self) -> QuestionCreate:
        validate_image_keys(self.type, self.prompt_image_id, self.config)
        if self.type == "multiple_choice":
            opts = self.config.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                raise ValueError(
                    "multiple_choice config must have 'options' list with at least 2 items"
                )
            if self.grading_type == "ACCURACY":
                pts = self.answer_data.get("answer_points")
                if not isinstance(pts, list) or len(pts) != len(opts):
                    raise ValueError(
                        "ACCURACY multiple_choice answer_data must have 'answer_points' list matching options length"
                    )
                if any(not isinstance(p, (int, float)) or p < 0 for p in pts):
                    raise ValueError(
                        "answer_points values must be non-negative numbers"
                    )
        if self.type == "true_false" and self.grading_type == "ACCURACY":
            pts = self.answer_data.get("answer_points")
            if not isinstance(pts, dict) or set(pts.keys()) != {"true", "false"}:
                raise ValueError(
                    "ACCURACY true_false answer_data must have 'answer_points' with 'true' and 'false' keys"
                )
        if self.type == "fill_in_the_blank" and self.grading_type == "ACCURACY":
            answers = self.answer_data.get("acceptedAnswers")
            if not isinstance(answers, list) or len(answers) == 0:
                raise ValueError(
                    "ACCURACY fill_in_the_blank answer_data must have 'acceptedAnswers' list with at least one item"
                )
            if any(not isinstance(a, str) or not a.strip() for a in answers):
                raise ValueError("acceptedAnswers entries must be non-empty strings")
            pts = self.answer_data.get("answerPoints")
            if not isinstance(pts, list) or len(pts) != len(answers):
                raise ValueError(
                    "ACCURACY fill_in_the_blank answer_data must have 'answerPoints' list matching acceptedAnswers length"
                )
            if any(not isinstance(p, (int, float)) or p < 0 for p in pts):
                raise ValueError("answerPoints values must be non-negative numbers")
            edit_dist = self.answer_data.get("editDistance", 0)
            if not isinstance(edit_dist, int) or edit_dist < 0:
                raise ValueError("editDistance must be a non-negative integer")
        if self.type == "multi_select":
            opts = self.config.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                raise ValueError(
                    "multi_select config must have 'options' list with at least 2 items"
                )
            if self.grading_type == "ACCURACY":
                pts = self.answer_data.get("answer_points")
                if not isinstance(pts, list) or len(pts) != len(opts):
                    raise ValueError(
                        "ACCURACY multi_select answer_data must have 'answer_points' list matching options length"
                    )
                if any(not isinstance(p, (int, float)) for p in pts):
                    raise ValueError("answer_points values must be numbers")
        if self.type == "put_in_order":
            validate_put_in_order(self.grading_type, self.config, self.answer_data)
        if self.type == "pin_the_spot":
            validate_pin_the_spot(self.grading_type, self.config, self.answer_data)
        return self


class QuestionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str | None = Field(
        None,
        pattern="^(multiple_choice|true_false|fill_in_the_blank|multi_select|put_in_order|pin_the_spot)$",
    )
    grading_type: str | None = Field(None, pattern="^(ACCURACY|COMPLETENESS)$")
    prompt: str | None = Field(None, min_length=1, max_length=2000)
    # Omitted keeps the stored value; an explicit null clears it (model_fields_set).
    prompt_image_id: str | None = None
    config: dict | None = None
    answer_data: dict | None = None
    time_limit_seconds: int | None = Field(None, ge=2, le=300)
    points_value: float | None = Field(None, ge=0, le=100000)
    order_index: int | None = Field(None, ge=0)


class QuestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    game_id: int
    type: str
    grading_type: str
    prompt: str
    prompt_image_id: str | None
    config: dict
    answer_data: dict
    time_limit_seconds: int
    points_value: float
    order_index: int
    created_at: datetime


class QuestionReorder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order: list[int] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Users (local accounts)
# ---------------------------------------------------------------------------


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(..., min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$")
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=72)
    email: EmailStr | None = None

    @field_validator("username")
    @classmethod
    def lower_username(cls, v: str) -> str:
        return v.lower()


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str | None = Field(
        None, min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_-]+$"
    )
    display_name: str | None = Field(None, min_length=1, max_length=255)
    email: EmailStr | None = None
    password: str | None = Field(None, min_length=8, max_length=72)
    role: str | None = Field(None, pattern="^(USER|ADMIN)$")

    @field_validator("username")
    @classmethod
    def lower_username(cls, v: str | None) -> str | None:
        return v.lower() if v is not None else None


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    username: str | None
    netid: str | None
    display_name: str | None
    email: str | None
    role: str
    created_at: datetime
    last_login: datetime | None


# ---------------------------------------------------------------------------
# Access management
# ---------------------------------------------------------------------------


class CourseAccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    course_id: int
    role: str = Field(..., pattern="^(HOST|PLAYER)$")


class GameAccessGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_id: int


class UserWithAccessResponse(UserResponse):
    course_access: list[dict]
    game_access: list[int]


# ---------------------------------------------------------------------------
# Sessions (admin view)
# ---------------------------------------------------------------------------


class AdminSessionItem(BaseModel):
    model_config = ConfigDict(from_attributes=False)
    session_id: str
    room_code: str
    status: str
    game_id: int
    game_title: str
    course_id: int
    course_name: str
    course_semester: str
    host_display_name: str | None
    created_at: datetime
    completed_at: datetime | None
    player_count: int
