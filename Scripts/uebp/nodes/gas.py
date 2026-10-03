"""uebp.nodes.gas -- GameplayAbilities."""

# The Gameplay Ability System (plugin GameplayAbilities). The C++ class is
# AbilitySystemBlueprintLibrary even though Python calls it AbilitySystemLibrary.

FN_ADD_GRANTED_TAG = "/Script/GameplayAbilities.AbilitySystemBlueprintLibrary.AddGrantedTag"
FN_GET_ASC = "/Script/GameplayAbilities.AbilitySystemBlueprintLibrary.GetAbilitySystemComponent"
FN_SEND_GAMEPLAY_EVENT = ("/Script/GameplayAbilities.AbilitySystemBlueprintLibrary"
                          ".SendGameplayEventToActor")

FN_APPLY_SPEC_TO_SELF = ("/Script/GameplayAbilities.AbilitySystemComponent"
                         ".BP_ApplyGameplayEffectSpecToSelf")
FN_EFFECT_COUNT = "/Script/GameplayAbilities.AbilitySystemComponent.GetGameplayEffectCount"
FN_GIVE_ABILITY = "/Script/GameplayAbilities.AbilitySystemComponent.K2_GiveAbility"
FN_MAKE_CONTEXT = "/Script/GameplayAbilities.AbilitySystemComponent.MakeEffectContext"
FN_MAKE_SPEC = "/Script/GameplayAbilities.AbilitySystemComponent.MakeOutgoingSpec"
FN_REMOVE_EFFECT = ("/Script/GameplayAbilities.AbilitySystemComponent"
                    ".RemoveActiveGameplayEffectBySourceEffect")
FN_REMOVE_GRANTING = ("/Script/GameplayAbilities.AbilitySystemComponent"
                      ".RemoveActiveEffectsWithGrantedTags")
FN_TAG_COUNT = "/Script/GameplayAbilities.AbilitySystemComponent.GetGameplayTagCount"

FN_AVATAR = "/Script/GameplayAbilities.GameplayAbility.GetAvatarActorFromActorInfo"
FN_END_ABILITY = "/Script/GameplayAbilities.GameplayAbility.K2_EndAbility"
