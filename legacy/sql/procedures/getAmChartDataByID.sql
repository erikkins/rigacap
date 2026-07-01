-- SqlProcedure: [dbo].[getAmChartDataByID]

set nocount on


select atwhen datesort, convert(varchar,atwhen,101) as atwhen, price, volume , dbo.fn50DMA(stockID, atwhen) [50DMA], dbo.fn200DMA(stockID, atwhen) [200DMA], dwap, dwap200
from stockdata
where stockID=@stockID
and atwhen between @startdate and dateadd(day,1,@enddate)
and price > 0
order by datesort asc
set nocount off
