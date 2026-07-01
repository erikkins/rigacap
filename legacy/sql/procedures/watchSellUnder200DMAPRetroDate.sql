-- SqlProcedure: [dbo].[watchSellUnder200DMAPRetroDate]

set nocount on

declare @watchID int, @stockID int, @shares decimal(8,3)
declare @lastPrice money
declare @200DMAP money
declare @buydate datetime
declare @BuyPrice money
declare @lastPrice2 money, @lastPrice3 money
declare @lastDataDate2 datetime
declare @diff int

select @watchID = watchID 
from Watch 
where ProcName = 'watchSellUnder200DMAPRetroDate'

exec addWatchHistory @watchID, @RunDate

select @StockID = stockID,
@shares = shares,
@BuyDate = atwhen
from StockBuy 
where BuyID=@BuyID

select @diff = datediff(day, @buydate, @rundate)
if @diff < 30
	begin
		return 0
	end

declare @splitdate datetime
declare @splitmult decimal(3,2)
declare @left int, @right int, @colloc int, @newprice money

			/*
			select top 200 @200DMAP = avg(price)
			from stockdata
			where atwhen < @RunDate
			and stockID = @StockID
			group by atwhen
			order by atwhen desc
			*/
			select @200DMAP = dbo.fn200DMA(@stockID, @RunDate)

			declare @undercount int
			declare @prices table
			(
				theprice money
			)
			insert into @prices
				select top 5 Price		
				from StockData sd
				where sd.StockID = @StockID
				and sd.AtWhen <= @RunDate
				order by sd.AtWhen DESC

			select @undercount= count(*)
			from @prices
			where theprice < @200DMAP
			if @undercount = 5
				begin
					--sell!
					exec saveAudit @RunDate, 'Below 200DMAP', @stockID, 'BELOW200DMAP'
					exec addSell @buyID, @watchID, @RunDate, @shares, 'Below 200DMAP'	
					PRINT 'Selling at Below 200DMAP' -- StockID:' + Convert(varchar, @stockID) + ' , BuyID:' + Convert(varchar,@BuyID) + ' , RunDate:' + Convert(varchar,@RunDate,101)
					return 1				
				end			

	return 0
