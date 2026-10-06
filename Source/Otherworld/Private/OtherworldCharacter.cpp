#include "OtherworldCharacter.h"

#include "OtherworldCharacterMovement.h"

AOtherworldCharacter::AOtherworldCharacter(const FObjectInitializer& ObjectInitializer)
	: Super(ObjectInitializer.SetDefaultSubobjectClass<UOtherworldCharacterMovement>(ACharacter::CharacterMovementComponentName))
{
}
