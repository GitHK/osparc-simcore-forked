# How do I run checks at regular intervals in the future?
#   - check at regular intervals, start when the time has arrived
#   - only schedule a new task if current task finished else skip this run and bump the timer
#   - this way we can aggressively schedule every 0.1 seconds a task that takes 10 seconds to run
#   - keeps track of this in Redis with a Desired state (and Current state) pattern

# How do I run a task get it's results and then do something else
#   - handler with code that I want to execute deferred
#   - logic to handle the result
#   - apply retry logic when the result is received (retry x times give up after x times etc...)
#   - keeps track of this in Redis with a Desired state (and Current state) pattern


from typing import Any

from faststream.redis import RedisBroker, RedisRouter

router = RedisRouter()

# create utility to apply router with corerct preofix and more form the original function so they are unique and we can decorate

# wrap below into a class and have everything available?
# how do we dynamically register this?


def _get_delivery_config(handler_name: str, prefix: str = __name__) -> dict[str, Any]:
    # NOTE: configure how to deliver subscribers and publishers
    # also adds the prefix of the current module
    return {"list": f"{prefix}_{handler_name}"}


@router.subscriber(**_get_delivery_config("request"))
@router.publisher(**_get_delivery_config("response"))
async def deferred_execution(name: str, user_id: int) -> str:
    return f"Hi {name}@{user_id}!"


@router.subscriber(**_get_delivery_config("response"))
async def result_handler(response: str) -> None:
    # now we can add rety in case of error and typing fancyness etc..
    # invokes message handler to take care of response
    print(f"Got: {response}")


async def send_emit_request(broker: RedisBroker, name: str, user_id: int) -> None:
    # use to send out a request chain
    await broker.publish(
        {"name": name, "user_id": user_id}, **_get_delivery_config("request")
    )
