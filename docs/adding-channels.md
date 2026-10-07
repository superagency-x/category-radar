# Adding Channels

To introduce a new retailer or price comparison engine:

1. **Define the Channel Adapter**:
   Create a new adapter in `src/category_radar/channels/<site>.py` implementing `ChannelAdapter`:

   ```python
   from .base import ChannelAdapter, register
   from ..models import RawListing

   @register("my_retailer")
   class MyRetailerAdapter(ChannelAdapter):
       def parse(self, html: str, *, channel: str, market: str, currency: str, rank_offset: int = 0) -> list[RawListing]:
           ...

       def next_page_url(self, html: str, current_url: str) -> str | None:
           ...
   ```

2. **Register in Configuration**:
   Add the channel entry to `config/airfryer.yaml`:

   ```yaml
   channels:
     my_retailer_de:
       market: DE
       adapter: my_retailer
       type: retailer
       start_url: https://www.example.com/category
       max_pages: 2
   ```

3. **Verify with Doctor**:
   Test fetching and parsing:
   ```bash
   radar doctor --channels my_retailer_de
   ```
