from safebox.core.services import VaultService
from safebox.core.transfer import TransferConversationStatus


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
