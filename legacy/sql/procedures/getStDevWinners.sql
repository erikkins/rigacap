-- SqlProcedure: [dbo].[getStDevWinners]

set nocount on

declare @yes bit
select @yes = 0

	select @yes = 1
	from stockdata
	where stockid=@stockID
	and price > dbo.fnPrice1MonthAgo(stockID,atwhen) + (5 * dbo.StdDev3Month(stockID,atwhen))
	--and dbo.StdDev1Month(stockID,atwhen) > @priceVariance * dbo.StdDev3Month(stockID,atwhen)
	and atwhen = @today
	and volume > 5 * dbo.fn50Volume(stockID,atwhen) 	
	and volume > 5000000
	and price > dbo.fn50DMA(stockID, atwhen)
	and price > dbo.fnPrice1WeekAgo(stockID,atwhen)
	and price > dbo.fnPrice1MonthAgo(stockID,atwhen)
	/*
	if @yes = 0
		BEGIN
			select @yes = 1
			from stockdata
			where stockid=@stockID
			and price > dbo.fnPrice1MonthAgo(stockID,atwhen) + (2 * dbo.StdDev3Month(stockID,atwhen))
			--and dbo.StdDev1Month(stockID,atwhen) > @priceVariance * dbo.StdDev3Month(stockID,atwhen)
			and atwhen = @today
			and volume > 1.1 * dbo.fn50Volume(stockID,atwhen) 	
			and volume > 5000000
			and price > dbo.fn50DMA(stockID, atwhen)
			and price > dbo.fnPrice1WeekAgo(stockID,atwhen)
			and price > dbo.fnPrice1MonthAgo(stockID,atwhen	)
		END
	*/
select @yes
