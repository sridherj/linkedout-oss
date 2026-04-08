# SPDX-License-Identifier: Apache-2.0
"""Core Pydantic schema for ProfileSkill."""
from datetime import datetime

from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field


class ProfileSkillSchema(BaseModel):
    id: Annotated[str, Field(description='Primary key')]
    crawled_profile_id: Annotated[str, Field(description='Profile this skill belongs to')]
    skill_name: Annotated[str, Field(description='Name of the skill')]
    endorsement_count: Annotated[int, Field(description='Number of endorsements', default=0)]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
