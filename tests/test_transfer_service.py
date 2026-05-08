import pytest

from safebox.core.services import VaultService
from safebox.core.transfer import TransferConversationStatus, TransferMessageSender


def test_service_creates_and_lists_transfer_conversations(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")

    conversation = service.create_transfer_conversation(
        title="祥磊的 iPhone 对话",
        device_name="祥磊的 iPhone",
    )

    conversations = service.list_transfer_conversations()

    assert conversations[0].id == conversation.id
    assert conversations[0].title == "祥磊的 iPhone 对话"
    assert conversations[0].device_name == "祥磊的 iPhone"
    assert conversations[0].status == TransferConversationStatus.ACTIVE


def test_service_closes_transfer_conversation(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="临时资料",
        device_name="安卓手机",
    )

    closed = service.close_transfer_conversation(conversation.id)

    assert closed.status == TransferConversationStatus.CLOSED
    assert closed.closed_at
    assert service.get_transfer_conversation(conversation.id).status == (
        TransferConversationStatus.CLOSED
    )


def test_service_searches_transfer_conversations(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    service.create_transfer_conversation(title="报销资料", device_name="祥磊的 iPhone")
    service.create_transfer_conversation(title="学习摘录", device_name="安卓手机")

    conversations = service.list_transfer_conversations("报销")

    assert [item.title for item in conversations] == ["报销资料"]


def test_service_adds_and_lists_transfer_text_messages(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )

    first = service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        text="发票图片稍后发你",
    )
    second = service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.DESKTOP,
        text="收到",
    )

    messages = service.list_transfer_messages(conversation.id)
    updated = service.get_transfer_conversation(conversation.id)

    assert [message.id for message in messages] == [first.id, second.id]
    assert [message.sender for message in messages] == [
        TransferMessageSender.PHONE,
        TransferMessageSender.DESKTOP,
    ]
    assert [message.text for message in messages] == ["发票图片稍后发你", "收到"]
    assert updated.message_count == 2


def test_service_rejects_empty_transfer_text_message(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )

    with pytest.raises(ValueError, match="Message text is required"):
        service.add_transfer_text_message(
            conversation.id,
            sender=TransferMessageSender.DESKTOP,
            text="   ",
        )


def test_service_rejects_messages_after_transfer_conversation_closes(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.close_transfer_conversation(conversation.id)

    with pytest.raises(ValueError, match="Transfer conversation is closed"):
        service.add_transfer_text_message(
            conversation.id,
            sender=TransferMessageSender.PHONE,
            text="还有一张图",
        )


def test_change_master_password_reencrypts_transfer_messages(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("old password")
    service.unlock("old password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        text="发票图片稍后发你",
    )

    service.change_master_password("old password", "new password")
    service.lock()
    service.unlock("new password")

    messages = service.list_transfer_messages(conversation.id)

    assert [message.text for message in messages] == ["发票图片稍后发你"]
