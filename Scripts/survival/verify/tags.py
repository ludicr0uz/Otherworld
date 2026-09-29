"""The gameplay tags: declared in the config, and registered with the engine."""

import os

import unreal

from combat.tuning import CONSUME_EVENT_TAG, HEALTH_DRAIN_TAG
from combat.verify.common import check
from survival.tuning import DEHYDRATED_TAG, STARVING_TAG

TAGS = (CONSUME_EVENT_TAG, HEALTH_DRAIN_TAG, STARVING_TAG, DEHYDRATED_TAG)
INI = os.path.join(os.path.dirname(__file__), "..", "..", "..", "Config",
                   "DefaultGameplayTags.ini")


def run():
    text = open(os.path.abspath(INI)).read()
    for tag in TAGS:
        check(f"DefaultGameplayTags.ini declares {tag}", f'Tag="{tag}"' in text)
        # A tag the manager does not know imports fine and compares as
        # invalid, and a pin literal holding one silently matches nothing.
        t = unreal.GameplayTag()
        t.import_text(f'(TagName="{tag}")')
        check(f"the engine has registered {tag}",
              unreal.GameplayTagLibrary.is_gameplay_tag_valid(t))
