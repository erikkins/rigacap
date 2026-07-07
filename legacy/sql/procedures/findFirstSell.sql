-- SqlProcedure: [dbo].[findFirstSell]

set nocount on

--get stockID from watch and buydate
declare @stockID int
declare @buyDate datetime
declare @buyPrice money
declare @currdate datetime
declare @today datetime
select @today = getdate()
declare @currprice money
declare @shares decimal(8,2)
declare @failcount int
declare @50dma money
declare @isKTR bit
declare @sellcomment varchar(100)

select @stockID=stockID, @buyDate=atwhen,
@shares=shares
from stockbuy
where buyID=@BuyID

select @failcount = 0

select @buyPrice = price
from stockData
where stockID=@stockID
and atWhen = @buyDate

select @currdate = @buydate
while @currdate < @today
	begin
		select @currprice = price
		from stockdata
		where stockID=@stockID
		and atwhen = @currdate

		select @50dma = dbo.fn50DMA(@stockID, @currdate)

		if @currprice is not null
			begin
				select @isKTR = dbo.fnIsKeyTrendReversal(@stockID, @currdate)
				if @isKTR is null
					begin
						select @isKTR = 0
					end
				--if (@currprice < (@buyprice * 0.92)) or (@currprice > (@buyprice * 1.4) or (@currprice < @50dma) or (@isKTR=1))
				if (@currprice < (@buyprice * 0.92)) or (@currprice > (@buyprice * 1.4) or (@isKTR=1))
				BEGIN
					if @isKTR=1
						begin
							select @sellcomment = 'KeyTrendReversal'
						end
					if @currprice < (@buyprice * 0.92)
						begin
							select @sellcomment = '8% down'
						end
					if @currprice >= (@buyprice * 1.4)
						begin
							select @sellcomment = '40% up'
						end

					exec addSell @buyID, -1000, @currdate, @shares, @sellcomment
					return
				END
			end		
		else
			begin
			Print 'Failing on ' + convert(varchar, @buyID)
			if @failcount > 20
				begin
					delete from stockbuy where buyID=@buyID
					return
				end
			select @failcount = @failcount + 1
			end
		select @currdate = dateadd(day,1,@currdate)
	end

set nocount off
