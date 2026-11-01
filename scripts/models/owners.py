"""Who may answer open questions per package in Confluence (state/owners.json)."""

from pydantic import Field

from .common import StrictModel


class Owner(StrictModel):
    name: str = Field(min_length=1, description="Name used when the doc cites this owner.")
    account_id: str = Field(min_length=1, description="Atlassian account id. Display names can be changed "
                                                      "by anyone for their own profile; the account id cannot.")


class OwnersFile(StrictModel):
    packages: dict[str, list[Owner]] = Field(default={}, description="Package name -> its owners.")
