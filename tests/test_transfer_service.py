import pytest

from safebox.core.services import VaultService
from safebox.core.transfer import (
    TransferConversationStatus,
    TransferMessageKind,
    TransferMessageSender,
)


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


def test_service_adds_and_lists_transfer_attachments(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )

    message, attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.IMAGE,
        filename="invoice.jpg",
        mime_type="image/jpeg",
        size_bytes=2048,
        storage_path="attachments/tc/invoice.jpg",
        sha256="abc123",
        text="发票截图",
    )

    messages = service.list_transfer_messages(conversation.id)
    attachments = service.list_transfer_attachments(conversation.id)
    updated = service.get_transfer_conversation(conversation.id)

    assert messages[0].id == message.id
    assert messages[0].kind == TransferMessageKind.IMAGE
    assert messages[0].attachment_id == attachment.id
    assert attachments[0].filename == "invoice.jpg"
    assert attachments[0].mime_type == "image/jpeg"
    assert attachments[0].size_bytes == 2048
    assert attachments[0].message_id == message.id
    assert updated.message_count == 1
    assert updated.attachment_count == 1


def test_transfer_attachment_note_export_uses_placeholder(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.IMAGE,
        filename="invoice.jpg",
        mime_type="image/jpeg",
        size_bytes=2048,
        storage_path="attachments/tc/invoice.jpg",
        sha256="abc123",
    )

    note = service.export_transfer_conversation_to_note(conversation.id)

    assert "[图片附件] invoice.jpg" in note.note
    assert "attachments/tc/invoice.jpg" not in note.note


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


def test_change_master_password_reencrypts_transfer_attachments(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("old password")
    service.unlock("old password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )

    service.change_master_password("old password", "new password")
    service.lock()
    service.unlock("new password")

    attachments = service.list_transfer_attachments(conversation.id)

    assert [attachment.filename for attachment in attachments] == ["invoice.pdf"]


def test_service_records_and_lists_download_history(vault_path, tmp_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    message, attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    saved_path = tmp_path / "invoice.pdf"
    saved_path.write_text("pdf", encoding="utf-8")

    record = service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=message.id,
        attachment_id=attachment.id,
        filename=attachment.filename,
        saved_path=saved_path,
        size_bytes=attachment.size_bytes,
    )

    history = service.list_download_history()

    assert history[0].id == record.id
    assert history[0].filename == "invoice.pdf"
    assert history[0].saved_path == str(saved_path)
    assert history[0].exists is True

    saved_path.unlink()

    assert service.list_download_history()[0].exists is False


def test_service_deletes_and_clears_download_history(vault_path, tmp_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    message, attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    first = service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=message.id,
        attachment_id=attachment.id,
        filename=attachment.filename,
        saved_path=tmp_path / "invoice.pdf",
        size_bytes=attachment.size_bytes,
    )
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=message.id,
        attachment_id=attachment.id,
        filename="copy.pdf",
        saved_path=tmp_path / "copy.pdf",
        size_bytes=attachment.size_bytes,
    )

    service.delete_download_history_record(first.id)

    assert [item.filename for item in service.list_download_history()] == ["copy.pdf"]

    service.clear_download_history()

    assert service.list_download_history() == []


def test_change_master_password_reencrypts_download_history(vault_path, tmp_path) -> None:
    service = VaultService(vault_path)
    service.initialize("old password")
    service.unlock("old password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    message, attachment = service.add_transfer_attachment_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        kind=TransferMessageKind.FILE,
        filename="invoice.pdf",
        mime_type="application/pdf",
        size_bytes=4096,
        storage_path="attachments/tc/invoice.pdf",
        sha256="abc123",
    )
    service.record_transfer_download(
        conversation_id=conversation.id,
        message_id=message.id,
        attachment_id=attachment.id,
        filename=attachment.filename,
        saved_path=tmp_path / "invoice.pdf",
        size_bytes=attachment.size_bytes,
    )

    service.change_master_password("old password", "new password")
    service.lock()
    service.unlock("new password")

    assert [item.filename for item in service.list_download_history()] == ["invoice.pdf"]


def test_transfer_conversation_exports_to_session_note(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        text="发票图片稍后发你",
    )
    service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.DESKTOP,
        text="收到",
    )

    note = service.export_transfer_conversation_to_note(conversation.id)
    updated = service.get_transfer_conversation(conversation.id)

    assert note.name == "报销资料"
    assert note.category == "会话"
    assert "手机 " in note.note
    assert "发票图片稍后发你" in note.note
    assert "\n\n电脑 " in note.note
    assert "收到" in note.note
    assert updated.note_id == note.id
    assert updated.note_sync_active is True
    assert updated.note_last_appended_message_id
    assert updated.status == TransferConversationStatus.TRANSFERRED


def test_exported_session_note_keeps_appending_until_conversation_closes(
    vault_path,
) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        text="第一条",
    )
    note = service.export_transfer_conversation_to_note(conversation.id)

    service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.DESKTOP,
        text="第二条",
    )
    appended_note = service.get_record(note.id)

    assert "第一条" in appended_note.note
    assert "第二条" in appended_note.note
    assert appended_note.note.count("\n\n") >= 1

    service.close_transfer_conversation(conversation.id)
    closed = service.get_transfer_conversation(conversation.id)

    assert closed.note_sync_active is False


def test_exported_session_note_stays_bound_after_conversation_closes(vault_path) -> None:
    service = VaultService(vault_path)
    service.initialize("master password")
    service.unlock("master password")
    conversation = service.create_transfer_conversation(
        title="报销资料",
        device_name="安卓手机",
    )
    service.add_transfer_text_message(
        conversation.id,
        sender=TransferMessageSender.PHONE,
        text="第一条",
    )
    note = service.export_transfer_conversation_to_note(conversation.id)

    service.close_transfer_conversation(conversation.id)
    closed = service.get_transfer_conversation(conversation.id)

    assert closed.note_id == note.id
    assert closed.note_sync_active is False
    assert closed.status == TransferConversationStatus.TRANSFERRED
