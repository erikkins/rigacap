-- SqlProcedure: [dbo].[zzzwatchBuyAbove200DMA]

--this is a buy watch, but we're not using the startdate ever...

declare @buydate datetime, @lastvolume float
declare @watchID int
declare @lastdma float
/***********************
OK, so 200DMA from the web is PRICE, we want VOLUME
So, we're not going to use the price one anymore, just ignore it
***********************/

select @watchID = watchID 
from Watch 
where ProcName = 'watchBuyAbove200DMA'

select top 200 volume into #200v
from StockData
where stockid=@stockID
order by atwhen desc

select @lastdma = convert(float,sum(volume))/200 from #200v

drop table #200v

select @lastvolume = LastVolume
from Stock s
inner join StockInteresting si on si.StockID = s.stockID
where s.stockid = @stockID

select @buydate = max(atwhen)
from StockData
where stockID = @stockID
	
	if @lastdma is not null and @lastvolume is not null
		begin
			if @lastdma > 0 and @lastvolume > 0
				begin
				--see if the last price exceeds the last 200dma
					if @lastvolume > @lastdma
						begin
						--if so, update the transaction to a buy and update the buy date
							--exec addBuy @stockID, @watchID, @buydate

						--we're just moving this stock to the holding pen
						exec hold @stockID, @buydate, 'ABOVE200DMA'

						/*
						now delete the record from StockInteresting
						since it was SO interesting we actually bought it
						...no need to buy it tomorrow too
						*/
							delete from StockInteresting
							where StockID = @StockID
						end
				end
		end
