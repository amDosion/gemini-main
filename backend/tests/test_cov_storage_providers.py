"""Coverage-focused, behaviour-asserting tests for the cloud storage providers.

Targets:
  * app.services.storage.tencent_provider.TencentProvider  (qcloud_cos COS)
  * app.services.storage.s3_provider.S3Provider             (boto3 S3 compatible)

These providers are thin async wrappers around the COS / boto3 SDKs. The only
external boundary is ``_create_client`` (the SDK client factory). We instantiate
the real provider classes with real config dicts and override ``_create_client``
to return a ``MagicMock`` that stands in for the SDK client. Every assertion
checks real provider behaviour: success/error mapping, URL construction, object
key normalisation, pagination loops, path-traversal rejection, config validation
and the supported/unsupported result envelopes. The SUT logic itself is never
mocked.

The COS exception classes are constructed for real: passing a ``dict`` as the
message to ``CosServiceError`` makes ``get_error_code`` / ``get_error_msg`` /
``get_status_code`` return controllable values (see qcloud_cos source).
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError
from qcloud_cos.cos_exception import CosClientError, CosServiceError

import app.services.storage.s3_provider as s3_mod
import app.services.storage.tencent_provider as tencent_mod
from app.services.storage.base import UploadResult
from app.services.storage.s3_provider import S3Provider
from app.services.storage.tencent_provider import TencentProvider


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ok_meta(status=200):
    return {"ResponseMetadata": {"HTTPStatusCode": status}}


def cos_service_error(code="NoSuchKey", message="missing", status=404):
    """A real CosServiceError with controllable code/message/status."""
    return CosServiceError(
        "GET",
        {"code": code, "message": message, "resource": "", "traceid": "", "requestid": ""},
        status,
    )


def s3_client_error(code="AccessDenied", message="denied", op="PutObject"):
    return ClientError(
        {"Error": {"Code": code, "Message": message}, "ResponseMetadata": {}},
        op,
    )


def make_tencent(**overrides):
    config = {
        "secret_id": "sid",
        "secret_key": "skey",
        "bucket": "mybucket",
        "region": "ap-guangzhou",
    }
    config.update(overrides)
    provider = TencentProvider(config)
    client = MagicMock(name="cos_client")
    provider._create_client = MagicMock(return_value=client)
    return provider, client


def make_s3(**overrides):
    config = {
        "access_key_id": "ak",
        "secret_access_key": "sk",
        "bucket": "mybucket",
        "region": "us-east-1",
    }
    config.update(overrides)
    provider = S3Provider(config)
    client = MagicMock(name="s3_client")
    provider._create_client = MagicMock(return_value=client)
    return provider, client


# ===========================================================================
# _create_client — real factory bodies (mock only the SDK constructors)
# ===========================================================================
class TestCreateClientFactories:
    def test_tencent_create_client_builds_cos_config(self):
        provider = TencentProvider(
            {"secret_id": "sid", "secret_key": "skey", "region": "ap-shanghai"}
        )
        with patch.object(tencent_mod, "CosConfig") as cfg, patch.object(
            tencent_mod, "CosS3Client"
        ) as cli:
            cfg.return_value = "cfg-obj"
            cli.return_value = "client-obj"
            result = provider._create_client()

        cfg.assert_called_once_with(Region="ap-shanghai", SecretId="sid", SecretKey="skey")
        cli.assert_called_once_with("cfg-obj")
        assert result == "client-obj"

    def test_s3_create_client_default_virtual_addressing(self):
        provider = S3Provider(
            {"access_key_id": "ak", "secret_access_key": "sk", "region": "eu-west-2"}
        )
        with patch.object(s3_mod, "boto3") as boto3_mock:
            boto3_mock.client.return_value = "s3-client"
            result = provider._create_client()

        assert result == "s3-client"
        _, kwargs = boto3_mock.client.call_args
        assert kwargs["service_name"] == "s3"
        assert kwargs["aws_access_key_id"] == "ak"
        assert kwargs["region_name"] == "eu-west-2"
        assert "endpoint_url" not in kwargs

    def test_s3_create_client_with_endpoint_and_path_style(self):
        provider = S3Provider(
            {
                "access_key_id": "ak",
                "secret_access_key": "sk",
                "endpoint": "https://minio.local",
                "force_path_style": True,
            }
        )
        with patch.object(s3_mod, "boto3") as boto3_mock:
            boto3_mock.client.return_value = "s3-client"
            provider._create_client()

        _, kwargs = boto3_mock.client.call_args
        assert kwargs["endpoint_url"] == "https://minio.local"


# ===========================================================================
# Tencent COS — upload
# ===========================================================================
class TestTencentUpload:
    async def test_upload_success_builds_default_url_and_metadata(self):
        provider, client = make_tencent()
        client.put_object.return_value = {**ok_meta(200), "ETag": '"abc123"'}

        result = await provider.upload("pic.png", b"data", "image/png")

        assert isinstance(result, UploadResult)
        assert result.success is True
        assert result.provider == "tencent-cos"
        # default prefix is uploads/, default url is the bucket cos domain
        assert result.url.startswith("https://mybucket.cos.ap-guangzhou.myqcloud.com/uploads/")
        assert result.url.endswith("_pic.png")
        assert result.metadata["bucket"] == "mybucket"
        assert result.metadata["etag"] == "abc123"
        assert result.metadata["object_name"].startswith("uploads/")
        # the SDK was actually called with the right bucket/body
        _, kwargs = client.put_object.call_args
        assert kwargs["Bucket"] == "mybucket"
        assert kwargs["Body"] == b"data"
        assert kwargs["ContentType"] == "image/png"

    async def test_upload_uses_path_prefix_and_custom_domain(self):
        provider, client = make_tencent(path_prefix="/media/", domain="https://cdn.example.com/")
        client.put_object.return_value = {**ok_meta(200), "ETag": '"e"'}

        result = await provider.upload("a.jpg", b"x", "image/jpeg")

        assert result.success is True
        assert result.url.startswith("https://cdn.example.com/media/")
        assert result.metadata["object_name"].startswith("media/")

    async def test_upload_missing_config_returns_error_without_calling_sdk(self):
        provider, client = make_tencent(bucket="")

        result = await provider.upload("a.png", b"x", "image/png")

        assert result.success is False
        assert "配置不完整" in result.error
        client.put_object.assert_not_called()

    async def test_upload_non_200_status_returns_error(self):
        provider, client = make_tencent()
        client.put_object.return_value = ok_meta(403)

        result = await provider.upload("a.png", b"x", "image/png")

        assert result.success is False
        assert "HTTP 403" in result.error

    async def test_upload_service_error_maps_code_and_message(self):
        provider, client = make_tencent()
        client.put_object.side_effect = cos_service_error("AccessDenied", "no perm", 403)

        result = await provider.upload("a.png", b"x", "image/png")

        assert result.success is False
        assert "服务错误" in result.error
        assert "AccessDenied" in result.error
        assert "no perm" in result.error

    async def test_upload_client_error_maps_message(self):
        provider, client = make_tencent()
        client.put_object.side_effect = CosClientError("network down")

        result = await provider.upload("a.png", b"x", "image/png")

        assert result.success is False
        assert "客户端错误" in result.error
        assert "network down" in result.error

    async def test_upload_generic_exception_is_caught(self):
        provider, client = make_tencent()
        client.put_object.side_effect = RuntimeError("boom")

        result = await provider.upload("a.png", b"x", "image/png")

        assert result.success is False
        assert "上传失败" in result.error
        assert "boom" in result.error


# ===========================================================================
# Tencent COS — delete
# ===========================================================================
class TestTencentDelete:
    async def test_delete_success_extracts_key_from_url(self):
        provider, client = make_tencent()
        client.delete_object.return_value = ok_meta(204)

        url = "https://mybucket.cos.ap-guangzhou.myqcloud.com/uploads/123_pic.png"
        ok = await provider.delete(url)

        assert ok is True
        _, kwargs = client.delete_object.call_args
        assert kwargs["Key"] == "uploads/123_pic.png"
        assert kwargs["Bucket"] == "mybucket"

    async def test_delete_no_bucket_returns_false(self):
        provider, client = make_tencent(bucket="")
        ok = await provider.delete("https://x/y.png")
        assert ok is False
        client.delete_object.assert_not_called()

    async def test_delete_empty_object_key_returns_false(self):
        provider, client = make_tencent()
        ok = await provider.delete("https://mybucket.cos.ap-guangzhou.myqcloud.com/")
        assert ok is False
        client.delete_object.assert_not_called()

    async def test_delete_service_error_returns_false(self):
        provider, client = make_tencent()
        client.delete_object.side_effect = cos_service_error()
        ok = await provider.delete("https://h/uploads/a.png")
        assert ok is False

    async def test_delete_unexpected_exception_returns_false(self):
        provider, client = make_tencent()
        client.delete_object.side_effect = RuntimeError("x")
        ok = await provider.delete("https://h/uploads/a.png")
        assert ok is False


# ===========================================================================
# Tencent COS — delete_path
# ===========================================================================
class TestTencentDeletePath:
    async def test_delete_path_missing_config(self):
        provider, _ = make_tencent(region="")
        res = await provider.delete_path("a/b.png")
        assert res == {"success": False, "supported": False, "message": "腾讯云 COS 配置不完整"}

    async def test_delete_single_file_success(self):
        provider, client = make_tencent()
        client.delete_object.return_value = ok_meta(200)
        res = await provider.delete_path("docs/a.png")
        assert res["success"] is True
        assert res["supported"] is True
        _, kwargs = client.delete_object.call_args
        assert kwargs["Key"] == "docs/a.png"

    async def test_delete_single_file_falls_back_to_url(self):
        provider, client = make_tencent()
        client.delete_object.return_value = ok_meta(204)
        res = await provider.delete_path(
            "", file_url="https://mybucket.cos.ap-guangzhou.myqcloud.com/uploads/z.png"
        )
        assert res["success"] is True
        _, kwargs = client.delete_object.call_args
        assert kwargs["Key"] == "uploads/z.png"

    async def test_delete_single_file_missing_path_and_url(self):
        provider, _ = make_tencent()
        res = await provider.delete_path("", file_url="")
        assert res == {"success": False, "supported": False, "message": "path is required"}

    async def test_delete_directory_root_rejected(self):
        provider, _ = make_tencent()
        res = await provider.delete_path("", is_directory=True)
        assert res["supported"] is False
        assert "根目录" in res["message"]

    async def test_delete_directory_paginates_and_deletes_all(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = [
            {"Contents": [{"Key": "docs/a"}, {"Key": "docs/b"}], "IsTruncated": "true", "NextMarker": "m1"},
            {"Contents": [{"Key": "docs/c"}], "IsTruncated": "false"},
        ]
        client.delete_object.return_value = ok_meta(200)

        res = await provider.delete_path("docs", is_directory=True)

        assert res["success"] is True
        assert client.delete_object.call_count == 3
        deleted = {c.kwargs["Key"] for c in client.delete_object.call_args_list}
        assert deleted == {"docs/a", "docs/b", "docs/c"}

    async def test_delete_directory_empty_returns_success(self):
        provider, client = make_tencent()
        client.list_objects.return_value = {"Contents": [], "IsTruncated": False}
        res = await provider.delete_path("empty", is_directory=True)
        assert res["success"] is True
        assert "为空" in res["message"]
        client.delete_object.assert_not_called()

    async def test_delete_path_value_error_from_traversal(self):
        provider, _ = make_tencent()
        res = await provider.delete_path("../etc", is_directory=True)
        assert res["supported"] is False
        assert "非法目录路径" in res["message"]

    async def test_delete_path_service_error_supported_true(self):
        provider, client = make_tencent()
        client.delete_object.side_effect = cos_service_error("E", "bad", 500)
        res = await provider.delete_path("docs/a.png")
        assert res["success"] is False
        assert res["supported"] is True
        assert "删除失败" in res["message"]


# ===========================================================================
# Tencent COS — rename_path
# ===========================================================================
class TestTencentRename:
    async def test_rename_missing_config(self):
        provider, _ = make_tencent(bucket="")
        res = await provider.rename_path("a.png", "b.png")
        assert res == {"success": False, "supported": False, "message": "腾讯云 COS 配置不完整"}

    async def test_rename_empty_new_name(self):
        provider, _ = make_tencent()
        res = await provider.rename_path("a.png", "  ")
        assert "new_name is required" in res["message"]

    async def test_rename_new_name_with_separator_rejected(self):
        provider, _ = make_tencent()
        res = await provider.rename_path("a.png", "sub/b.png")
        assert "路径分隔符" in res["message"]

    async def test_rename_file_success_copies_then_deletes(self):
        provider, client = make_tencent()
        # source exists (head ok), target missing (404), then copy+delete
        client.head_object.side_effect = [ok_meta(200), cos_service_error("NoSuchKey", "x", 404)]
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is True
        client.copy_object.assert_called_once()
        client.delete_object.assert_called_once()
        _, copy_kwargs = client.copy_object.call_args
        assert copy_kwargs["Key"] == "docs/new.png"
        assert copy_kwargs["CopySource"]["Key"] == "docs/old.png"

    async def test_rename_file_source_missing(self):
        provider, client = make_tencent()
        client.head_object.side_effect = cos_service_error("NoSuchKey", "x", 404)
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert "源文件不存在" in res["message"]
        client.copy_object.assert_not_called()

    async def test_rename_file_target_exists(self):
        provider, client = make_tencent()
        client.head_object.side_effect = [ok_meta(200), ok_meta(200)]
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert "目标文件已存在" in res["message"]
        client.copy_object.assert_not_called()

    async def test_rename_same_key_is_noop_success(self):
        provider, client = make_tencent()
        res = await provider.rename_path("a.png", "a.png")
        assert res["success"] is True
        client.head_object.assert_not_called()

    async def test_rename_directory_success(self):
        provider, client = make_tencent()
        # target prefix check -> empty; then listing source -> two keys
        client.list_objects.side_effect = [
            {"Contents": []},  # target existence check
            {"Contents": [{"Key": "docs/old/a"}, {"Key": "docs/old/b"}], "IsTruncated": False},
        ]
        res = await provider.rename_path("docs/old", "new", is_directory=True)
        assert res["success"] is True
        assert client.copy_object.call_count == 2
        assert client.delete_object.call_count == 2
        new_keys = {c.kwargs["Key"] for c in client.copy_object.call_args_list}
        assert new_keys == {"docs/new/a", "docs/new/b"}

    async def test_rename_directory_target_exists(self):
        provider, client = make_tencent()
        client.list_objects.return_value = {"Contents": [{"Key": "docs/new/x"}]}
        res = await provider.rename_path("docs/old", "new", is_directory=True)
        assert res["success"] is False
        assert "目标目录已存在" in res["message"]

    async def test_rename_directory_source_missing(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = [
            {"Contents": []},  # target check empty
            {"Contents": [], "IsTruncated": False},  # source listing empty
        ]
        res = await provider.rename_path("docs/old", "new", is_directory=True)
        assert res["success"] is False
        assert "源目录不存在" in res["message"]

    async def test_rename_traversal_value_error(self):
        provider, _ = make_tencent()
        res = await provider.rename_path("../x", "y")
        assert res["supported"] is False
        assert "非法目录路径" in res["message"]

    async def test_rename_directory_paginates_source_listing(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = [
            {"Contents": []},  # target existence check empty
            {"Contents": [{"Key": "docs/old/a"}], "IsTruncated": "true", "NextMarker": "m1"},
            {"Contents": [{"Key": "docs/old/sub/b"}], "IsTruncated": "false"},
        ]
        res = await provider.rename_path("docs/old", "new", is_directory=True)
        assert res["success"] is True
        new_keys = {c.kwargs["Key"] for c in client.copy_object.call_args_list}
        assert new_keys == {"docs/new/a", "docs/new/sub/b"}
        assert client.delete_object.call_count == 2

    async def test_rename_service_error_supported_true(self):
        provider, client = make_tencent()
        client.head_object.side_effect = cos_service_error("InternalError", "boom", 500)
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert res["supported"] is True
        assert "重命名失败" in res["message"]


# ===========================================================================
# Tencent COS — browse
# ===========================================================================
class TestTencentBrowse:
    async def test_browse_missing_config(self):
        provider, _ = make_tencent(secret_id="")
        res = await provider.browse("")
        assert res["supported"] is False
        assert res["items"] == []
        assert "配置不完整" in res["message"]

    async def test_browse_lists_dirs_and_files_sorted(self):
        provider, client = make_tencent()
        client.list_objects.return_value = {
            "CommonPrefixes": [{"Prefix": "zeta/"}, {"Prefix": "alpha/"}],
            "Contents": [
                {"Key": "b.png", "Size": 10, "LastModified": "2020"},
                {"Key": "folder/", "Size": 0},  # directory marker, skipped
            ],
            "IsTruncated": "false",
        }
        res = await provider.browse("")
        assert res["supported"] is True
        # directories first (sorted), then files
        names = [i["name"] for i in res["items"]]
        assert names == ["alpha", "zeta", "b.png"]
        types = [i["entry_type"] for i in res["items"]]
        assert types == ["directory", "directory", "file"]
        file_item = res["items"][2]
        assert file_item["size"] == 10
        assert file_item["url"].endswith("/b.png")

    async def test_browse_has_more_derives_cursor_from_last_key(self):
        provider, client = make_tencent()
        client.list_objects.return_value = {
            "Contents": [{"Key": "a.png", "Size": 1}, {"Key": "c.png", "Size": 2}],
            "IsTruncated": True,
        }
        res = await provider.browse("", limit=2, cursor="prev")
        assert res["has_more"] is True
        assert res["next_cursor"] == "c.png"
        _, kwargs = client.list_objects.call_args
        assert kwargs["Marker"] == "prev"

    async def test_browse_value_error_from_traversal(self):
        provider, _ = make_tencent()
        res = await provider.browse("../secret")
        assert res["supported"] is False
        assert "非法目录路径" in res["message"]

    async def test_browse_service_error(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = cos_service_error("E", "boom", 500)
        res = await provider.browse("")
        assert res["supported"] is False
        assert "浏览失败" in res["message"]


# ===========================================================================
# Tencent COS — count_items & test
# ===========================================================================
class TestTencentCountAndTest:
    async def test_count_missing_config(self):
        provider, _ = make_tencent(region="")
        res = await provider.count_items("")
        assert res["supported"] is False
        assert res["total_count"] is None

    async def test_count_paginates_and_sums(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = [
            {
                "CommonPrefixes": [{"Prefix": "d1/"}],
                "Contents": [{"Key": "a"}, {"Key": "skip/"}],
                "IsTruncated": "true",
                "NextMarker": "m1",
            },
            {"CommonPrefixes": [], "Contents": [{"Key": "b"}], "IsTruncated": "false"},
        ]
        res = await provider.count_items("dir")
        assert res["supported"] is True
        # 1 dir + 1 file (skip/ ignored) + 1 file = 3
        assert res["total_count"] == 3

    async def test_count_service_error(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = cos_service_error("E", "x", 500)
        res = await provider.count_items("")
        assert res["supported"] is False
        assert "统计失败" in res["message"]

    async def test_test_missing_config(self):
        provider, _ = make_tencent(secret_key="")
        res = await provider.test()
        assert res.success is False
        assert "配置不完整" in res.error

    async def test_test_success(self):
        provider, client = make_tencent()
        client.list_objects.return_value = ok_meta(200)
        res = await provider.test()
        assert res.success is True
        assert res.provider == "tencent-cos"

    async def test_test_non_200(self):
        provider, client = make_tencent()
        client.list_objects.return_value = ok_meta(500)
        res = await provider.test()
        assert res.success is False
        assert "连接测试失败" in res.error

    async def test_test_service_error(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = cos_service_error("AccessDenied", "no", 403)
        res = await provider.test()
        assert res.success is False
        assert "AccessDenied" in res.error

    async def test_test_client_error(self):
        provider, client = make_tencent()
        client.list_objects.side_effect = CosClientError("conn fail")
        res = await provider.test()
        assert res.success is False
        assert "客户端错误" in res.error


# ===========================================================================
# S3 — _create_client / URL building (no SDK call)
# ===========================================================================
class TestS3UrlBuilding:
    def test_public_url_virtual_hosted_default(self):
        provider = S3Provider({"bucket": "b", "region": "eu-west-1"})
        assert provider._build_public_url("k/x.png") == "https://b.s3.eu-west-1.amazonaws.com/k/x.png"

    def test_public_url_path_style(self):
        provider = S3Provider({"bucket": "b", "region": "eu-west-1", "force_path_style": True})
        assert provider._build_public_url("k.png") == "https://s3.eu-west-1.amazonaws.com/b/k.png"

    def test_public_url_custom_endpoint_virtual(self):
        provider = S3Provider({"bucket": "b", "endpoint": "https://minio.local"})
        assert provider._build_public_url("k.png") == "https://b.minio.local/k.png"

    def test_public_url_custom_endpoint_path_style(self):
        provider = S3Provider(
            {"bucket": "b", "endpoint": "http://minio.local/", "force_path_style": True}
        )
        assert provider._build_public_url("k.png") == "https://minio.local/b/k.png"

    def test_public_url_custom_domain_overrides(self):
        provider = S3Provider({"bucket": "b", "custom_domain": "https://cdn.x.com/"})
        assert provider._build_public_url("k.png") == "https://cdn.x.com/k.png"


# ===========================================================================
# S3 — upload
# ===========================================================================
class TestS3Upload:
    async def test_upload_success(self):
        provider, client = make_s3()
        client.put_object.return_value = {**ok_meta(200), "ETag": '"deadbeef"'}

        res = await provider.upload("file.bin", b"payload", "application/octet-stream")

        assert res.success is True
        assert res.provider == "s3-compatible"
        assert res.url.startswith("https://mybucket.s3.us-east-1.amazonaws.com/uploads/")
        assert res.metadata["etag"] == "deadbeef"
        assert res.metadata["object_key"].startswith("uploads/")
        _, kwargs = client.put_object.call_args
        assert kwargs["Body"] == b"payload"

    async def test_upload_with_path_prefix(self):
        provider, client = make_s3(path_prefix="/img/")
        client.put_object.return_value = {**ok_meta(200), "ETag": '"e"'}
        res = await provider.upload("a.png", b"x", "image/png")
        assert res.success is True
        assert res.metadata["object_key"].startswith("img/")

    async def test_upload_missing_config(self):
        provider, client = make_s3(access_key_id="")
        res = await provider.upload("a.png", b"x", "image/png")
        assert res.success is False
        assert "配置不完整" in res.error
        client.put_object.assert_not_called()

    async def test_upload_non_200(self):
        provider, client = make_s3()
        client.put_object.return_value = ok_meta(500)
        res = await provider.upload("a.png", b"x", "image/png")
        assert res.success is False
        assert "HTTP 500" in res.error

    async def test_upload_client_error_maps_code_message(self):
        provider, client = make_s3()
        client.put_object.side_effect = s3_client_error("AccessDenied", "nope")
        res = await provider.upload("a.png", b"x", "image/png")
        assert res.success is False
        assert "AccessDenied" in res.error
        assert "nope" in res.error

    async def test_upload_endpoint_connection_error(self):
        provider, client = make_s3(endpoint="https://minio.local")
        client.put_object.side_effect = EndpointConnectionError(endpoint_url="https://minio.local")
        res = await provider.upload("a.png", b"x", "image/png")
        assert res.success is False
        assert "连接错误" in res.error
        assert "minio.local" in res.error

    async def test_upload_generic_exception(self):
        provider, client = make_s3()
        client.put_object.side_effect = ValueError("weird")
        res = await provider.upload("a.png", b"x", "image/png")
        assert res.success is False
        assert "上传失败" in res.error


# ===========================================================================
# S3 — delete
# ===========================================================================
class TestS3Delete:
    async def test_delete_success(self):
        provider, client = make_s3()
        client.delete_object.return_value = ok_meta(204)
        ok = await provider.delete("https://mybucket.s3.us-east-1.amazonaws.com/uploads/x.png")
        assert ok is True
        _, kwargs = client.delete_object.call_args
        assert kwargs["Key"] == "uploads/x.png"

    async def test_delete_no_bucket(self):
        provider, client = make_s3(bucket="")
        ok = await provider.delete("https://x/y.png")
        assert ok is False
        client.delete_object.assert_not_called()

    async def test_delete_empty_key(self):
        provider, client = make_s3()
        ok = await provider.delete("https://mybucket.s3.us-east-1.amazonaws.com/")
        assert ok is False

    async def test_delete_client_error(self):
        provider, client = make_s3()
        client.delete_object.side_effect = s3_client_error()
        ok = await provider.delete("https://h/uploads/x.png")
        assert ok is False

    async def test_delete_generic_exception(self):
        provider, client = make_s3()
        client.delete_object.side_effect = RuntimeError("x")
        ok = await provider.delete("https://h/uploads/x.png")
        assert ok is False


# ===========================================================================
# S3 — delete_path
# ===========================================================================
class TestS3DeletePath:
    async def test_missing_config(self):
        provider, _ = make_s3(bucket="")
        res = await provider.delete_path("a")
        assert res == {"success": False, "supported": False, "message": "S3 配置不完整"}

    async def test_single_file_success(self):
        provider, client = make_s3()
        client.delete_object.return_value = ok_meta(200)
        res = await provider.delete_path("docs/a.png")
        assert res["success"] is True
        _, kwargs = client.delete_object.call_args
        assert kwargs["Key"] == "docs/a.png"

    async def test_single_file_fallback_url(self):
        provider, client = make_s3()
        client.delete_object.return_value = ok_meta(204)
        res = await provider.delete_path(
            "", file_url="https://mybucket.s3.us-east-1.amazonaws.com/uploads/z.png"
        )
        assert res["success"] is True

    async def test_single_file_missing_both(self):
        provider, _ = make_s3()
        res = await provider.delete_path("", file_url="")
        assert res == {"success": False, "supported": False, "message": "path is required"}

    async def test_directory_root_rejected(self):
        provider, _ = make_s3()
        res = await provider.delete_path("", is_directory=True)
        assert "根目录" in res["message"]

    async def test_directory_paginated_batch_delete(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = [
            {"Contents": [{"Key": "d/a"}, {"Key": "d/b"}], "IsTruncated": True, "NextContinuationToken": "t1"},
            {"Contents": [{"Key": "d/c"}], "IsTruncated": False},
        ]
        res = await provider.delete_path("d", is_directory=True)
        assert res["success"] is True
        # delete_objects called once (all keys < 1000 -> single chunk)
        client.delete_objects.assert_called_once()
        _, kwargs = client.delete_objects.call_args
        sent_keys = {o["Key"] for o in kwargs["Delete"]["Objects"]}
        assert sent_keys == {"d/a", "d/b", "d/c"}

    async def test_directory_empty(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}
        res = await provider.delete_path("d", is_directory=True)
        assert res["success"] is True
        assert "为空" in res["message"]
        client.delete_objects.assert_not_called()

    async def test_traversal_value_error(self):
        provider, _ = make_s3()
        res = await provider.delete_path("../x", is_directory=True)
        assert res["supported"] is False
        assert "非法目录路径" in res["message"]

    async def test_client_error_supported_true(self):
        provider, client = make_s3()
        client.delete_object.side_effect = s3_client_error("InternalError", "oops")
        res = await provider.delete_path("a.png")
        assert res["success"] is False
        assert res["supported"] is True
        assert "InternalError" in res["message"]


# ===========================================================================
# S3 — rename_path
# ===========================================================================
class TestS3Rename:
    async def test_missing_config(self):
        provider, _ = make_s3(bucket="")
        res = await provider.rename_path("a.png", "b.png")
        assert res["message"] == "S3 配置不完整"

    async def test_empty_new_name(self):
        provider, _ = make_s3()
        res = await provider.rename_path("a.png", "")
        assert "new_name is required" in res["message"]

    async def test_new_name_with_separator(self):
        provider, _ = make_s3()
        res = await provider.rename_path("a.png", "x\\y")
        assert "路径分隔符" in res["message"]

    async def test_file_rename_success(self):
        provider, client = make_s3()
        # source head ok, target head -> NoSuchKey
        client.head_object.side_effect = [ok_meta(200), s3_client_error("NoSuchKey", "x", "HeadObject")]
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is True
        client.copy_object.assert_called_once()
        client.delete_object.assert_called_once()
        _, kwargs = client.copy_object.call_args
        assert kwargs["Key"] == "docs/new.png"
        assert kwargs["CopySource"] == {"Bucket": "mybucket", "Key": "docs/old.png"}

    async def test_file_rename_source_missing(self):
        provider, client = make_s3()
        client.head_object.side_effect = s3_client_error("404", "x", "HeadObject")
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert "源文件不存在" in res["message"]

    async def test_file_rename_target_exists(self):
        provider, client = make_s3()
        client.head_object.side_effect = [ok_meta(200), ok_meta(200)]
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert "目标文件已存在" in res["message"]

    async def test_rename_same_key_noop(self):
        provider, client = make_s3()
        res = await provider.rename_path("a.png", "a.png")
        assert res["success"] is True
        client.head_object.assert_not_called()

    async def test_directory_rename_success(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = [
            {"KeyCount": 0},  # target existence check
            {"Contents": [{"Key": "d/old/a"}, {"Key": "d/old/b"}], "IsTruncated": False},
        ]
        res = await provider.rename_path("d/old", "new", is_directory=True)
        assert res["success"] is True
        assert client.copy_object.call_count == 2
        assert client.delete_object.call_count == 2
        new_keys = {c.kwargs["Key"] for c in client.copy_object.call_args_list}
        assert new_keys == {"d/new/a", "d/new/b"}

    async def test_directory_rename_target_exists(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = {"KeyCount": 1}
        res = await provider.rename_path("d/old", "new", is_directory=True)
        assert res["success"] is False
        assert "目标目录已存在" in res["message"]

    async def test_directory_rename_source_missing(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = [
            {"KeyCount": 0},
            {"Contents": [], "IsTruncated": False},
        ]
        res = await provider.rename_path("d/old", "new", is_directory=True)
        assert res["success"] is False
        assert "源目录不存在" in res["message"]

    async def test_rename_client_error_supported(self):
        provider, client = make_s3()
        client.head_object.side_effect = s3_client_error("InternalError", "boom", "HeadObject")
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert res["supported"] is True
        assert "InternalError" in res["message"]

    async def test_directory_rename_paginates_source(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = [
            {"KeyCount": 0},  # target existence check
            {"Contents": [{"Key": "d/old/a"}], "IsTruncated": True, "NextContinuationToken": "t1"},
            {"Contents": [{"Key": "d/old/sub/b"}], "IsTruncated": False},
        ]
        res = await provider.rename_path("d/old", "new", is_directory=True)
        assert res["success"] is True
        new_keys = {c.kwargs["Key"] for c in client.copy_object.call_args_list}
        assert new_keys == {"d/new/a", "d/new/sub/b"}
        assert client.delete_object.call_count == 2

    async def test_rename_generic_exception_supported(self):
        provider, client = make_s3()
        client.head_object.side_effect = RuntimeError("kaboom")
        res = await provider.rename_path("docs/old.png", "new.png")
        assert res["success"] is False
        assert res["supported"] is True
        assert "重命名失败" in res["message"]


# ===========================================================================
# S3 — browse
# ===========================================================================
class TestS3Browse:
    async def test_missing_config(self):
        provider, _ = make_s3(secret_access_key="")
        res = await provider.browse("")
        assert res["supported"] is False
        assert "配置不完整" in res["message"]

    async def test_browse_dirs_and_files_with_iso_date(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = {
            "CommonPrefixes": [{"Prefix": "zfolder/"}, {"Prefix": "afolder/"}],
            "Contents": [
                {"Key": "file.txt", "Size": 7, "LastModified": datetime(2021, 1, 2, 3, 4, 5)},
                {"Key": "marker/"},  # trailing slash skipped
            ],
            "IsTruncated": True,
            "NextContinuationToken": "tok",
        }
        res = await provider.browse("")
        assert res["supported"] is True
        names = [i["name"] for i in res["items"]]
        assert names == ["afolder", "zfolder", "file.txt"]
        file_item = res["items"][-1]
        assert file_item["entry_type"] == "file"
        assert file_item["updated_at"] == "2021-01-02T03:04:05"
        assert res["has_more"] is True
        assert res["next_cursor"] == "tok"

    async def test_browse_passes_continuation_token(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = {"Contents": [], "IsTruncated": False}
        await provider.browse("sub", cursor="cur")
        _, kwargs = client.list_objects_v2.call_args
        assert kwargs["ContinuationToken"] == "cur"
        assert kwargs["Prefix"] == "sub/"

    async def test_browse_traversal(self):
        provider, _ = make_s3()
        res = await provider.browse("../x")
        assert res["supported"] is False
        assert "非法目录路径" in res["message"]

    async def test_browse_client_error(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = s3_client_error("AccessDenied", "no")
        res = await provider.browse("")
        assert res["supported"] is False
        assert "AccessDenied" in res["message"]


# ===========================================================================
# S3 — count_items & test
# ===========================================================================
class TestS3CountAndTest:
    async def test_count_missing_config(self):
        provider, _ = make_s3(bucket="")
        res = await provider.count_items("")
        assert res["supported"] is False
        assert res["total_count"] is None

    async def test_count_paginates(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = [
            {
                "CommonPrefixes": [{"Prefix": "d1/"}],
                "Contents": [{"Key": "a"}, {"Key": "skip/"}],
                "IsTruncated": True,
                "NextContinuationToken": "t",
            },
            {"CommonPrefixes": [], "Contents": [{"Key": "b"}], "IsTruncated": False},
        ]
        res = await provider.count_items("dir")
        assert res["supported"] is True
        assert res["total_count"] == 3  # 1 dir + a + b

    async def test_count_truncated_without_token_breaks(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = {
            "Contents": [{"Key": "a"}],
            "IsTruncated": True,
            # no NextContinuationToken -> loop must break
        }
        res = await provider.count_items("")
        assert res["supported"] is True
        assert res["total_count"] == 1

    async def test_count_client_error(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = s3_client_error("E", "x")
        res = await provider.count_items("")
        assert res["supported"] is False
        assert "统计失败" in res["message"]

    async def test_test_missing_config(self):
        provider, _ = make_s3(bucket="")
        res = await provider.test()
        assert res.success is False
        assert "配置不完整" in res.error

    async def test_test_success_includes_object_count(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = {**ok_meta(200), "KeyCount": 5}
        res = await provider.test()
        assert res.success is True
        assert res.metadata["object_count"] == 5

    async def test_test_non_200(self):
        provider, client = make_s3()
        client.list_objects_v2.return_value = ok_meta(403)
        res = await provider.test()
        assert res.success is False
        assert "连接测试失败" in res.error

    async def test_test_client_error(self):
        provider, client = make_s3()
        client.list_objects_v2.side_effect = s3_client_error("AccessDenied", "no")
        res = await provider.test()
        assert res.success is False
        assert "AccessDenied" in res.error

    async def test_test_endpoint_connection_error(self):
        provider, client = make_s3(endpoint="https://minio.local")
        client.list_objects_v2.side_effect = EndpointConnectionError(endpoint_url="https://minio.local")
        res = await provider.test()
        assert res.success is False
        assert "连接错误" in res.error
        assert "minio.local" in res.error
