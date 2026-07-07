-- SqlProcedure: [dbo].[watchBuyNewHigh]

--this is a buy watch, but we're not using the startdate ever...

--we're only intersted in stocks sitting in the holding pen that are above the 200DMAV
if not exists (select * from HoldingPen where stockID = @stockID and code ='WITHIN5%')
	begin
		return
		/*
		if not exists (select * from HoldingPen where StockID = @StockID and code='ABOVE50DMA')
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

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyNewHigh'

exec addWatchHistory @watchID, @now


declare @lastPrice money
declare @buydate datetime

declare @52WeekHigh money
select @52WeekHigh = [52WeekHigh], @ticker = ticker, @buydate = lastdatadate, @lastprice = lastprice
from Stock 
where StockID = @StockID

if @52WeekHigh is null
	begin
		select @audit = @ticker + ' 52 week high is null.'
		exec saveAudit @now,  @audit, @stockID
		return
	end

if @lastprice < 10.00
	begin
		return
	end

if @lastprice >= @52WeekHigh
	begin
		--declare @comment varchar(1000)
		--select @comment =  'Price exceeded 52 Week High of ' + convert(varchar,@52WeekHigh)
		--exec addbuy @stockID, @watchID, @buydate,@comment
		exec hold @stockID, 'NEWHIGH'
		exec unhold @stockID, 'WITHIN5%'

		select @audit = @ticker + ' hit 52 week high (' + convert(varchar,@lastprice) + ' is >= than ' + convert(varchar,@52WeekHigh) + ')'
		exec saveAudit @now,  @audit, @stockID, 'NEWHIGH', 'I'
	end
return
