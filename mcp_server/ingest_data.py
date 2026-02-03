import clickhouse_connect
import os
import time
import requests
import subprocess

def wait_for_clickhouse(host, port):
    client = None
    while client is None:
        try:
            client = clickhouse_connect.get_client(host=host, port=port)
            print("Connected to ClickHouse")
        except Exception as e:
            print(f"Waiting for ClickHouse... {e}")
            time.sleep(2)
    return client

def ingest():
    host = os.getenv('CLICKHOUSE_HOST', 'localhost')
    client = wait_for_clickhouse(host, 8123)

    client.command("CREATE DATABASE IF NOT EXISTS datasets")

    # Hits table schema
    hits_schema = """
    CREATE TABLE IF NOT EXISTS datasets.hits_v1 (
        WatchID UInt64, JavaEnable UInt8, Title String, GoodEvent Int16, EventTime DateTime,
        EventDate Date, CounterID UInt32, ClientIP UInt32, ClientIP6 FixedString(16),
        RegionID UInt32, UserID UInt64, CounterClass Int8, OS UInt8, UserAgent UInt8,
        URL String, Referer String, URLDomain String, RefererDomain String, Refresh UInt8,
        IsRobot UInt8, RefererCategories Array(UInt16), URLCategories Array(UInt16),
        URLRegions Array(UInt32), RefererRegions Array(UInt32), ResolutionWidth UInt16,
        ResolutionHeight UInt16, ResolutionDepth UInt8, FlashMajor UInt8, FlashMinor UInt8,
        FlashMinor2 String, NetMajor UInt8, NetMinor UInt8, UserAgentMajor UInt16,
        UserAgentMinor FixedString(2), CookieEnable UInt8, JavascriptEnable UInt8,
        IsMobile UInt8, MobilePhone UInt8, MobilePhoneModel String, Params String,
        IPNetworkID UInt32, TraficSourceID Int8, SearchEngineID UInt16, SearchPhrase String,
        AdvEngineID UInt8, IsArtifical UInt8, WindowClientWidth UInt16, WindowClientHeight UInt16,
        ClientTimeZone Int16, ClientEventTime DateTime, SilverlightVersion1 UInt8,
        SilverlightVersion2 UInt8, SilverlightVersion3 UInt32, SilverlightVersion4 UInt16,
        PageCharset String, CodeVersion UInt32, IsLink UInt8, IsDownload UInt8,
        IsNotBounce UInt8, FUniqID UInt64, HID UInt32, IsOldCounter UInt8, IsEvent UInt8,
        IsParameter UInt8, DontCountHits UInt8, WithHash UInt8, HitColor FixedString(1),
        UTCEventTime DateTime, Age UInt8, Sex UInt8, Income UInt8, Interests UInt16,
        Robotness UInt8, GeneralInterests Array(UInt16), RemoteIP UInt32,
        RemoteIP6 FixedString(16), WindowName Int32, OpenerName Int32, HistoryLength Int16,
        BrowserLanguage FixedString(2), BrowserCountry FixedString(2), SocialNetwork String,
        SocialAction String, HTTPError UInt16, SendTiming Int32, DNSTiming Int32,
        ConnectTiming Int32, ResponseStartTiming Int32, ResponseEndTiming Int32,
        FetchTiming Int32, RedirectTiming Int32, DOMInteractiveTiming Int32,
        DOMContentLoadedTiming Int32, DOMCompleteTiming Int32, LoadEventStartTiming Int32,
        LoadEventEndTiming Int32, NSToDOMContentLoadedTiming Int32, FirstPaintTiming Int32,
        RedirectCount Int8, SocialSourceNetworkID UInt8, SocialSourcePage String,
        ParamPrice Int64, ParamOrderID String, ParamCurrency FixedString(3),
        ParamCurrencyID UInt16, GoalsReached Array(UInt32), OpenstatServiceName String,
        OpenstatCampaignID String, OpenstatAdID String, OpenstatSourceID String,
        UTMSource String, UTMMedium String, UTMCampaign String, UTMContent String,
        UTMTerm String, FromTag String, HasGCLID UInt8, RefererHash UInt64,
        URLHash UInt64, CLID UInt32, YCLID UInt64, ShareService String, ShareURL String,
        ShareTitle String, ParsedParams Nested(Key1 String, Key2 String, Key3 String,
        Key4 String, Key5 String, ValueDouble Float64), IslandID FixedString(16),
        RequestNum UInt32, RequestTry UInt8
    ) ENGINE = MergeTree()
    PARTITION BY toYYYYMM(EventDate)
    ORDER BY (CounterID, EventDate, intHash32(UserID))
    SAMPLE BY intHash32(UserID)
    """
    client.command(hits_schema)

    # Visits table schema
    visits_schema = """
    CREATE TABLE IF NOT EXISTS datasets.visits_v1 (
        CounterID UInt32, StartDate Date, Sign Int8, IsNew UInt8, VisitID UInt64,
        UserID UInt64, StartTime DateTime, Duration UInt32, UTCStartTime DateTime,
        PageViews Int32, Hits Int32, IsBounce UInt8, Referer String, StartURL String,
        RefererDomain String, StartURLDomain String, EndURL String, LinkURL String,
        IsDownload UInt8, TraficSourceID Int8, SearchEngineID UInt16, SearchPhrase String,
        AdvEngineID UInt8, PlaceID Int32, RefererCategories Array(UInt16),
        URLCategories Array(UInt16), URLRegions Array(UInt32), RefererRegions Array(UInt32),
        IsYandex UInt8, GoalReachesDepth Int32, GoalReachesURL Int32, GoalReachesAny Int32,
        SocialSourceNetworkID UInt8, SocialSourcePage String, MobilePhoneModel String,
        ClientEventTime DateTime, RegionID UInt32, ClientIP UInt32, ClientIP6 FixedString(16),
        RemoteIP UInt32, RemoteIP6 FixedString(16), IPNetworkID UInt32,
        SilverlightVersion3 UInt32, CodeVersion UInt32, ResolutionWidth UInt16,
        ResolutionHeight UInt16, UserAgentMajor UInt16, UserAgentMinor UInt16,
        WindowClientWidth UInt16, WindowClientHeight UInt16, SilverlightVersion2 UInt8,
        SilverlightVersion4 UInt16, FlashVersion3 UInt16, FlashVersion4 UInt16,
        ClientTimeZone Int16, OS UInt8, UserAgent UInt8, ResolutionDepth UInt8,
        FlashMajor UInt8, FlashMinor UInt8, NetMajor UInt8, NetMinor UInt8,
        MobilePhone UInt8, SilverlightVersion1 UInt8, Age UInt8, Sex UInt8,
        Income UInt8, JavaEnable UInt8, CookieEnable UInt8, JavascriptEnable UInt8,
        IsMobile UInt8, BrowserLanguage UInt16, BrowserCountry UInt16, Interests UInt16,
        Robotness UInt8, GeneralInterests Array(UInt16), Params Array(String),
        Goals Nested(ID UInt32, Serial UInt32, EventTime DateTime, Price Int64,
        OrderID String, CurrencyID UInt32), WatchIDs Array(UInt64), ParamSumPrice Int64,
        ParamCurrency FixedString(3), ParamCurrencyID UInt16, ClickLogID UInt64,
        ClickEventID Int32, ClickGoodEvent Int32, ClickEventTime DateTime,
        ClickPriorityID Int32, ClickPhraseID Int32, ClickPageID Int32, ClickPlaceID Int32,
        ClickTypeID Int32, ClickResourceID Int32, ClickCost UInt32, ClickClientIP UInt32,
        ClickDomainID UInt32, ClickURL String, ClickAttempt UInt8, ClickOrderID UInt32,
        ClickBannerID UInt32, ClickMarketCategoryID UInt32, ClickMarketPP UInt32,
        ClickMarketCategoryName String, ClickMarketPPName String,
        ClickAWAPSCampaignName String, ClickPageName String, ClickTargetType UInt16,
        ClickTargetPhraseID UInt64, ClickContextType UInt8, ClickSelectType Int8,
        ClickOptions String, ClickGroupBannerID Int32, OpenstatServiceName String,
        OpenstatCampaignID String, OpenstatAdID String, OpenstatSourceID String,
        UTMSource String, UTMMedium String, UTMCampaign String, UTMContent String,
        UTMTerm String, FromTag String, HasGCLID UInt8, FirstVisit DateTime,
        PredLastVisit Date, LastVisit Date, TotalVisits UInt32,
        TraficSource Nested(ID Int8, SearchEngineID UInt16, AdvEngineID UInt8,
        PlaceID UInt16, SocialSourceNetworkID UInt8, Domain String, SearchPhrase String,
        SocialSourcePage String), Attendance FixedString(16), CLID UInt32,
        YCLID UInt64, NormalizedRefererHash UInt64, SearchPhraseHash UInt64,
        RefererDomainHash UInt64, NormalizedStartURLHash UInt64,
        StartURLDomainHash UInt64, NormalizedEndURLHash UInt64, TopLevelDomain UInt64,
        URLScheme UInt64, OpenstatServiceNameHash UInt64, OpenstatCampaignIDHash UInt64,
        OpenstatAdIDHash UInt64, OpenstatSourceIDHash UInt64, UTMSourceHash UInt64,
        UTMMediumHash UInt64, UTMCampaignHash UInt64, UTMContentHash UInt64,
        UTMTermHash UInt64, FromHash UInt64, WebVisorEnabled UInt8, WebVisorActivity UInt32,
        ParsedParams Nested(Key1 String, Key2 String, Key3 String, Key4 String,
        Key5 String, ValueDouble Float64), Market Nested(Type UInt8, GoalID UInt32,
        OrderID String, OrderPrice Int64, PP UInt32, DirectPlaceID UInt32,
        DirectOrderID UInt32, DirectBannerID UInt32, GoodID String, GoodName String,
        GoodQuantity Int32, GoodPrice Int64), IslandID FixedString(16)
    ) ENGINE = CollapsingMergeTree(Sign)
    PARTITION BY toYYYYMM(StartDate)
    ORDER BY (CounterID, StartDate, intHash32(UserID), VisitID)
    SAMPLE BY intHash32(UserID)
    """
    client.command(visits_schema)

    # Ingesting data
    # We use shell commands to take advantage of xz-utils and piping
    print("Ingesting hits_v1...")
    hits_url = "https://datasets.clickhouse.com/hits/tsv/hits_v1.tsv.xz"
    ingest_cmd = f"curl -s {hits_url} | unxz | clickhouse-client --host {host} --database datasets --query 'INSERT INTO hits_v1 FORMAT TSV'"
    # Wait, clickhouse-client is not installed in the container yet.
    # I should use HTTP interface or install it.

    # Alternative: use requests and stream to ClickHouse via HTTP
    def stream_to_clickhouse(url, table):
        print(f"Streaming {url} to {table}...")
        # Since unxz is needed, we'll use a subprocess to pipe
        process = subprocess.Popen(f"curl -s {url} | unxz", shell=True, stdout=subprocess.PIPE)

        # ClickHouse HTTP interface for INSERT
        ch_url = f"http://{host}:8123/?query=INSERT+INTO+datasets.{table}+FORMAT+TSV"
        response = requests.post(ch_url, data=process.stdout)
        if response.status_code == 200:
            print(f"Successfully ingested {table}")
        else:
            print(f"Error ingesting {table}: {response.text}")

    # Check if data already exists
    hits_count = client.command("SELECT count() FROM datasets.hits_v1")
    if hits_count == 0:
        stream_to_clickhouse(hits_url, "hits_v1")
    else:
        print(f"hits_v1 already has {hits_count} rows")

    print("Ingesting visits_v1...")
    visits_url = "https://datasets.clickhouse.com/visits/tsv/visits_v1.tsv.xz"
    visits_count = client.command("SELECT count() FROM datasets.visits_v1")
    if visits_count == 0:
        stream_to_clickhouse(visits_url, "visits_v1")
    else:
        print(f"visits_v1 already has {visits_count} rows")

if __name__ == "__main__":
    ingest()
