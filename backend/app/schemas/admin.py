from __future__ import annotations

import math
from datetime import datetime

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


PTS_MAX_URL_LEN = 1_500_000
PTS_MAX_IMAGE_SIDE = 20_000
_PTS_DATA_URL_PREFIXES = tuple(
    f"data:image/{fmt};base64," for fmt in ("png", "jpeg", "gif", "webp")
)


def _is_number(value: object) -> bool:
    """A real int or float (bools excluded: True is an int in Python), and finite."""
    return (
        type(value) in (int, float) and math.isfinite(value)  # type: ignore[arg-type]
    )


def _is_unit(value: object) -> bool:
    return _is_number(value) and 0 <= value <= 1  # type: ignore[operator]


def pin_aspect(config: dict) -> float:
    """Image height / width, from a config that passed validate_pin_the_spot."""
    return config["image_height"] / config["image_width"]


def validate_pin_the_spot(grading_type: str, config: dict, answer_data: dict) -> None:
    """Structural checks for a pin_the_spot question; raises ValueError on the first failure.

    Shared by QuestionCreate.validate_structure and authoring_service.update_question (which
    validates the merged values, since QuestionUpdate only sees a partial body).
    """
    config = config or {}
    answer_data = answer_data or {}
    if set(config) != {"image_url", "image_width", "image_height"}:
        raise ValueError(
            'Pin the Spot config must contain exactly "image_url", "image_width" and "image_height"'
        )
    url = config["image_url"]
    if not isinstance(url, str) or not (
        url.startswith(("http://", "https://"))
        or url.startswith(_PTS_DATA_URL_PREFIXES)
    ):
        raise ValueError(
            "Image must be an http(s) URL or a PNG, JPEG, GIF or WebP data URL"
        )
    if len(url) > PTS_MAX_URL_LEN:
        raise ValueError("Image is too large; use a smaller image")
    for key in ("image_width", "image_height"):
        side = config[key]
        if type(side) is not int or not (1 <= side <= PTS_MAX_IMAGE_SIDE):
            raise ValueError(
                "Image width and height must be whole numbers from 1 to 20000"
            )

    if not answer_data:
        if grading_type == "ACCURACY":
            raise ValueError(
                "Pin the Spot needs a target and radii for ACCURACY grading"
            )
        return
    if set(answer_data) != {"target", "r_full", "r_zero"}:
        raise ValueError(
            'Pin the Spot answer_data must contain exactly "target", "r_full" and "r_zero"'
        )
    target = answer_data["target"]
    if (
        not isinstance(target, dict)
        or set(target) != {"x", "y"}
        or not _is_unit(target["x"])
        or not _is_unit(target["y"])
    ):
        raise ValueError("Target must be {x, y} with numbers from 0 to 1")
    r_full, r_zero = answer_data["r_full"], answer_data["r_zero"]
    if not _is_number(r_full) or not _is_number(r_zero):
        raise ValueError("Radii must be numbers")
    diagonal = math.hypot(1.0, pin_aspect(config))
    if not (0 < r_full < r_zero <= diagonal):
        raise ValueError(
            "Radii must satisfy 0 < full-credit radius < zero-credit radius ≤ the image diagonal"
        )


class QuestionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str = Field(
        ...,
        pattern="^(multiple_choice|true_false|fill_in_the_blank|multi_select|put_in_order|pin_the_spot)$",
    )
    grading_type: str = Field(..., pattern="^(ACCURACY|COMPLETENESS)$")
    prompt: str = Field(..., min_length=1, max_length=2000)
    config: dict = Field(default_factory=dict)
    answer_data: dict = Field(default_factory=dict)
    time_limit_seconds: int = Field(30, ge=2, le=300)
    points_value: float = Field(1.0, ge=0, le=100000)
    order_index: int | None = Field(None, ge=0)

    @model_validator(mode="after")
    def validate_structure(self) -> QuestionCreate:
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
