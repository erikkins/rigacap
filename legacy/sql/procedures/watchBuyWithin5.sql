-- SqlProcedure: [dbo].[watchBuyWithin5]

--this is a buy watch, but we're not using the startdate ever...

--we're only intersted in stocks sitting in the holding pen that are above the 50DMAV
if not exists (select * from HoldingPen where stockID = @stockID and code ='ABOVE50DMA')
	begin
		return
		/*
		--we also allow checking for existing stocks in the within5% code (in case they fall off)
		if not exists(select * from HoldingPen where stockID = @stockID and code = 'WITHIN5%')
			begin
				return
			end
		*/
	end

declare @watchID int
declare @ticker varchar(5)
declare @now datetime
select @now = getdate()
declare @audit varchar(8000)

exec addWatchHistory @watchID, @now


select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyWithin5'

declare @52WH money

select @52WH = max(price)
from StockData where stockID = @stockID
and atwhen > dateadd(year, -1, getdate())

declare @lastPrice money
declare @buydate datetime
select @lastprice = lastprice, @ticker = ticker, @buydate = lastdatadate
from stock
where stockID = @stockID

if @lastprice < 10.00
	begin
		return
	end

if @lastprice >= @52WH * .95
	begin
		--promote
		exec hold @stockID, @buydate, 'WITHIN5%'
		exec unhold @stockID, 'ABOVE50DMA'


		select @audit = @ticker + ' promoted from ABOVE50DMA to WITHIN5% (' + convert(varchar,@lastprice) + ' is within 5% of ' + convert(varchar, @52WH) + ')' 
		exec saveAudit @now,  @audit, @stockID
	end
else
	begin
		--demote
		exec hold @stockID, @buydate, 'ABOVE50DMA'
		exec unhold @stockID, 'WITHIN5%'

		select @audit = @ticker + ' demoted from WITHIN5% to ABOVE50DMA'
		exec saveAudit @now,  @audit, @stockID
	end
return
