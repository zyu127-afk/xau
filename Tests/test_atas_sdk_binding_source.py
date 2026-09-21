from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_atas_sdk_project_targets_supported_runtimes_and_local_sdk():
    text = (ROOT / "ATAS" / "GoldTradingDataBridge.ATAS" / "GoldTradingDataBridge.ATAS.csproj").read_text(encoding="utf-8")
    assert "net8.0-windows;net10.0-windows" in text
    assert "ATAS.Indicators.dll" in text
    assert "ATAS.DataFeedsCore.dll" in text
    assert "AtasInstallDir" in text


def test_atas_indicator_binds_live_callbacks_and_defaults_mbo_off():
    text = (ROOT / "ATAS" / "GoldTradingDataBridge.ATAS" / "GoldTradingBridgeIndicator.cs").read_text(encoding="utf-8")
    for required in (
        "OnNewTrade",
        "OnBestBidAskChanged",
        "MarketDepthsChanged",
        "SubscribeMarketByOrderData",
        "OnMarketByOrdersChanged",
        "InstrumentInfo",
        "BridgeHost",
    ):
        assert required in text
    assert "EnableMbo { get; set; } = false" in text
    assert "_mboActive = true" in text
    assert "catch" in text and "_mboActive = false" in text


def test_atas_deployer_refuses_unverified_binary():
    text = (ROOT / "Tools" / "deploy_atas.ps1").read_text(encoding="utf-8")
    assert "dotnet build" in text
    assert "ATAS.Indicators.dll" in text
    assert "ATAS.DataFeedsCore.dll" in text
    assert "No unverified DLL was deployed" in text
    assert "atas-binding.json" in text
